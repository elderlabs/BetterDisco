import gevent
import time

from collections import namedtuple
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException

from disco.gateway.encoding import ENCODERS
from disco.gateway.packets import OPCode
from disco.types.base import cached_property
from disco.util.emitter import Emitter
from disco.util.logging import LoggingClass
from disco.util.websocket import Websocket
from disco.voice.packets import VoiceOPCode
from disco.voice.udp import AudioCodecs, RTPPayloadTypes, UDPVoiceClient


class SpeakingFlags:
    NONE = 0
    VOICE = 1 << 0
    SOUNDSHARE = 1 << 1
    PRIORITY = 1 << 2


class VoiceState:
    DISCONNECTED = 'DISCONNECTED'
    AWAITING_ENDPOINT = 'AWAITING_ENDPOINT'
    AUTHENTICATING = 'AUTHENTICATING'
    CONNECTING = 'CONNECTING'
    CONNECTED = 'CONNECTED'
    VOICE_DISCONNECTED = 'VOICE_DISCONNECTED'
    VOICE_CONNECTING = 'VOICE_CONNECTING'
    VOICE_CONNECTED = 'VOICE_CONNECTED'
    NO_ROUTE = 'NO_ROUTE'
    ICE_CHECKING = 'ICE_CHECKING'
    RECONNECTING = 'RECONNECTING'
    AUTHENTICATED = 'AUTHENTICATED'


VoiceSpeaking = namedtuple('VoiceSpeaking', [
    'client',
    'user_id',
    'speaking',
    'soundshare',
    'priority',
])


class VoiceException(Exception):
    def __init__(self, msg, client):
        self.voice_client = client
        super(VoiceException, self).__init__(msg)


class VoiceClient(LoggingClass):
    VOICE_GATEWAY_VERSION = 7

    SUPPORTED_MODES = {
         # 'aead_xchacha20_poly1305_rtpsize',
         'xsalsa20_poly1305',
         'xsalsa20_poly1305_lite',
         'xsalsa20_poly1305_lite_rtpsize',
         'xsalsa20_poly1305_suffix',
    }

    def __init__(self, client, server_id, is_dm=False, max_reconnects=5, encoder='json'):
        super(VoiceClient, self).__init__()

        self.client = client
        self.server_id = server_id
        self.channel_id = None
        self.is_dm = is_dm
        self.encoder = ENCODERS[encoder]
        self.max_reconnects = max_reconnects
        self.video_enabled = False
        self.media = None

        # Set the VoiceClient in the state's voice clients
        self.client.state.voice_clients[self.server_id] = self

        # Bind to some WS packets
        self.packets = Emitter()
        self.packets.on(VoiceOPCode.READY, self.on_voice_ready)
        self.packets.on(VoiceOPCode.HEARTBEAT, self.handle_heartbeat)
        self.packets.on(VoiceOPCode.SESSION_DESCRIPTION, self.on_voice_sdp)
        self.packets.on(VoiceOPCode.SPEAKING, self.on_voice_speaking)
        self.packets.on(VoiceOPCode.HEARTBEAT_ACK, self.handle_heartbeat_acknowledge)
        self.packets.on(VoiceOPCode.HELLO, self.on_voice_hello)
        self.packets.on(VoiceOPCode.RESUMED, self.on_voice_resumed)
        self.packets.on(VoiceOPCode.CLIENT_DISCONNECT, self.on_voice_client_disconnect)
        self.packets.on(VoiceOPCode.CODECS, self.on_voice_codecs)

        # State + state change emitter
        self.state = VoiceState.DISCONNECTED
        self.state_emitter = Emitter()

        # Connection metadata
        self.token = None
        self.endpoint = None
        self.ssrc = None
        self.ip = None
        self.port = None
        self.enc_modes = None
        self.experiments = None
        self.streams = None
        self.sdp = None
        self.mode = None
        self.udp = None
        self.audio_codec = None
        self.video_codec = None
        self.transport_id = None

        # Websocket connection
        self.ws = None

        self._session_id = None
        self._reconnects = 0
        self._heartbeat_task = None
        self._heartbeat_acknowledged = True
        self._identified = False
        self._safe_reconnect_state = False

        # Latency
        self._last_heartbeat = 0
        self.latency = -1

        # SSRCs
        self.audio_ssrcs = {}

    def __repr__(self):
        return '<VoiceClient guild_id={} channel_id={}>'.format(self.server_id, self.channel_id)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.server_id)

    @cached_property
    def channel(self):
        return self.client.state.channels.get(self.channel_id)

    @property
    def user_id(self):
        return self.client.state.me.id

    @property
    def ssrc_audio(self):
        return self.ssrc

    @property
    def ssrc_video(self):
        return self.ssrc + 1

    @property
    def ssrc_rtx(self):
        return self.ssrc + 2

    @property
    def ssrc_rtcp(self):
        return self.ssrc + 3

    def set_state(self, state):
        self.log.debug('[{}] state {} -> {}'.format(self.channel_id, self.state, state))
        prev_state = self.state
        self.state = state
        self.state_emitter.emit(state, prev_state)

    def set_endpoint(self, endpoint):
        endpoint = endpoint.split(':', 1)[0]
        if self.endpoint == endpoint:
            return

        self.log.info('[{}] {} ({})'.format(self.channel_id, self.state, endpoint))

        self.endpoint = endpoint

        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.close()
            self.ws = None

        self._identified = False

    def set_token(self, token):
        if self.token == token:
            return
        self.token = token
        if not self._identified:
            self.connect_and_run()

    def connect_and_run(self, gateway_url=None):
        if not gateway_url:
            gateway_url = f'wss://{self.endpoint}'
        gateway_url += f'/?v={self.VOICE_GATEWAY_VERSION}&encoding={self.encoder.TYPE}'

        self.ws = Websocket(gateway_url)
        self.ws.emitter.on('on_open', self.on_open)
        self.ws.emitter.on('on_error', self.on_error)
        self.ws.emitter.on('on_close', self.on_close)
        self.ws.emitter.on('on_message', self.on_message)
        self.ws.run_forever()

    def heartbeat_task(self, interval):
        while True:
            if not self._heartbeat_acknowledged:
                self.log.warning('[{}] WS Received HEARTBEAT without HEARTBEAT_ACK, reconnecting...'.format(self.channel_id))
                self._heartbeat_acknowledged = True
                self.ws.close(status=4000)
                self.on_close(0, 'HEARTBEAT failure')
                return
            self._last_heartbeat = time.perf_counter()

            self.send(VoiceOPCode.HEARTBEAT, time.time())
            self._heartbeat_acknowledged = False
            gevent.sleep(interval / 1000)

    def handle_heartbeat(self, _):
        self.send(VoiceOPCode.HEARTBEAT, time.time())

    def handle_heartbeat_acknowledge(self, _):
        self.log.debug('[{}] Received WS HEARTBEAT_ACK'.format(self.channel_id))
        self._heartbeat_acknowledged = True
        self.latency = float('{:.2f}'.format((time.perf_counter() - self._last_heartbeat) * 1000))

    def set_speaking(self, voice=False, soundshare=False, priority=False, delay=0):
        value = SpeakingFlags.NONE
        if voice:
            value |= SpeakingFlags.VOICE
        if soundshare:
            value |= SpeakingFlags.SOUNDSHARE
        if priority:
            value |= SpeakingFlags.PRIORITY

        self.send(VoiceOPCode.SPEAKING, {
            'speaking': value,
            'delay': delay,
            'ssrc': self.ssrc,
        })

    def set_voice_state(self, channel_id, mute=False, deaf=False, video=False):
        if self.server_id in self.client.state.voice_clients:
            self._safe_reconnect_state = True
        if channel_id and self.media:
            try:
                self.media.pause()
            except:
                pass
        self.client.gw.send(OPCode.VOICE_STATE_UPDATE, {
            'self_mute': bool(mute),
            'self_deaf': bool(deaf),
            'self_video': bool(video),
            'guild_id': None if self.is_dm else self.server_id,
            'channel_id': channel_id,
        })
        return

    def send(self, op, data):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.log.debug('[{}] sending OP {} (data = {})'.format(self.channel_id, op, data))
            self.ws.send(self.encoder.encode({'op': op, 'd': data}), self.encoder.OPCODE)
        else:
            self.log.debug('[{}] dropping because WS is closed OP {} (data = {})'.format(self.channel_id, op, data))

    def on_voice_client_disconnect(self, data):
        for ssrc in self.audio_ssrcs.keys():
            if self.audio_ssrcs[ssrc] == int(data['user_id']):
                del self.audio_ssrcs[ssrc]
                break

    def on_voice_codecs(self, data):
        self.audio_codec = data['audio_codec']
        self.video_codec = data['video_codec']
        if 'media_session_id' in data.keys():
            self.transport_id = data['media_session_id']

        # Set the UDP's RTP Audio Header's Payload Type
        self.udp.set_audio_codec(data['audio_codec'])

    def on_voice_hello(self, packet):
        self.log.info('[{}] Received Voice HELLO payload, starting heartbeater'.format(self.channel_id))
        self._heartbeat_task = gevent.spawn(self.heartbeat_task, packet['heartbeat_interval'])
        self.set_state(VoiceState.AUTHENTICATED)

    def on_voice_ready(self, data):
        self.log.info('[{}] Received READY payload, RTC connecting'.format(self.channel_id))
        self.set_state(VoiceState.CONNECTING)
        self.ssrc = data['ssrc']
        self.audio_ssrcs[self.ssrc] = self.client.state.me.id
        self.ip = data['ip']
        self.port = data['port']
        self.enc_modes = data['modes']
        self.experiments = data['experiments']
        self.streams = data['streams']
        self._identified = True

        for mode in self.enc_modes:
            if mode in self.SUPPORTED_MODES:
                self.mode = mode
                self.log.debug('[{}] Selected mode {}'.format(self.channel_id, mode))
                break
        else:
            raise Exception('Failed to find a supported voice mode')

        self.log.debug('[{}] Attempting IP discovery over UDP to {}:{}'.format(self.channel_id, self.ip, self.port))
        self.udp = UDPVoiceClient(self)
        ip, port = self.udp.connect(self.ip, self.port)

        if not ip:
            self.log.error('[{}] Failed to discover bot IP, perhaps a network configuration error is present.'.format(self.channel_id))
            self.disconnect()
            return

        codecs = []

        # Sending discord our available codecs and rtp payload type for it
        for idx, codec in enumerate(AudioCodecs):
            codecs.append({
                'name': codec,
                'type': 'audio',
                'priority': (idx + 1) * 1000,
                'payload_type': RTPPayloadTypes.get(codec).value,
            })

        self.log.debug('[{}] IP discovery completed ({}:{}), sending SELECT_PROTOCOL'.format(self.channel_id, ip, port))
        self.send(VoiceOPCode.SELECT_PROTOCOL, {
            'protocol': 'udp',
            'data': {
                'address': ip,
                'port': port,
                'mode': self.mode,
            },
            'codecs': codecs,
            'experiments': [],
        })
        self.send(VoiceOPCode.CLIENT_CONNECT, {
            'audio_ssrc': self.ssrc,
            'video_ssrc': 0,
            'rtx_ssrc': 0,
        })

    def on_voice_resumed(self, data):
        self.log.info('[{}] WS Resumed'.format(self.channel_id))
        self.set_state(VoiceState.CONNECTED)
        self._reconnects = 0
        if self.media:
            self.media.resume()

    def on_voice_sdp(self, sdp):
        self.log.info('[{}] Received session description; connected'.format(self.channel_id))

        self.mode = sdp['mode']  # UDP-only, does not apply to webRTC
        self.audio_codec = sdp['audio_codec']
        self.video_codec = sdp['video_codec']
        self.transport_id = sdp['media_session_id']  # analytics
        # self.sdp = sdp['sdp']  # webRTC only
        # self.keyframe_interval = sdp['keyframe_interval']

        # Set the UDP's RTP Audio Header's Payload Type
        self.udp.set_audio_codec(sdp['audio_codec'])

        # Create a secret box for encryption/decryption
        self.udp.setup_encryption(bytes(bytearray(sdp['secret_key'])))  # UDP only

        self.set_state(VoiceState.CONNECTED)

        self._reconnects = 0

        if self._safe_reconnect_state:
            self._safe_reconnect_state = False
            try:
                if self.media:
                    self.media.pause()
                    self.media.resume()
            except AttributeError:
                pass

    def on_voice_speaking(self, data):
        user_id = int(data['user_id'])

        self.audio_ssrcs[data['ssrc']] = user_id

        # Maybe rename speaking to voice in future
        payload = VoiceSpeaking(
            client=self,
            user_id=user_id,
            speaking=bool(data['speaking'] & SpeakingFlags.VOICE),
            soundshare=bool(data['speaking'] & SpeakingFlags.SOUNDSHARE),
            priority=bool(data['speaking'] & SpeakingFlags.PRIORITY),
        )

        self.client.gw.events.emit('VoiceSpeaking', payload)

    def on_message(self, msg):
        try:
            data = self.encoder.decode(msg)
            self.packets.emit(data['op'], data['d'])
        except Exception:
            self.log.exception('Failed to parse voice gateway message: ')

    def on_error(self, error):
        if isinstance(error, WebSocketTimeoutException):
            return self.log.error('[{}] WS has timed out. An upstream connection issue is likely present.'.format(self.channel_id))
        if not isinstance(error, WebSocketConnectionClosedException):
            self.log.error('[{}] WS received error: {}'.format(self.channel_id, error))

    def on_open(self):
        if self._identified:
            self.send(VoiceOPCode.RESUME, {
                'server_id': self.server_id,
                'session_id': self._session_id,
                'token': self.token,
            })
        else:
            self.send(VoiceOPCode.IDENTIFY, {
                'server_id': self.server_id,
                'user_id': self.user_id,
                'session_id': self._session_id,
                'token': self.token,
                'video': self.video_enabled,
            })

    def on_close(self, code=None, reason=None):
        gevent.sleep(0.001)
        if self.media:
            self.media.pause()
        self.log.info('[{}] WS Closed: {}{}({})'.format(self.channel_id, f'[{code}] ' if code else '', f'{reason} ' if reason else '', self._reconnects))

        if self._heartbeat_task:
            self.log.info('[{}] WS Closed: killing heartbeater'.format(self.channel_id))
            self._heartbeat_task.kill()
            self._heartbeat_task = None

        self.ws = None
        self._heartbeat_acknowledged = True

        # If we killed the connection, don't try resuming
        if self.state == VoiceState.DISCONNECTED:
            return

        if not code and self._safe_reconnect_state or (code and code in (4009, 4015)):
            self.log.info('[{}] Attempting WS resumption'.format(self.channel_id))
        self.set_state(VoiceState.RECONNECTING)
        self._reconnects += 1

        if self.max_reconnects and self._reconnects > self.max_reconnects:
            self.log.error('[{}] Failed to reconnect after {} attempts, giving up'.format(self.channel_id, self.max_reconnects))
            return self.disconnect()

        # Check if code is not None, was not from us
        if code and (4000 < code <= 4016 or code in (1000, 1001)):
            self._identified = False
            try:
                del self.client.state.voice_states[self.server_id]
            except KeyError:
                pass

            if self.udp and self.udp.connected:
                self.udp.disconnect()

            # every other code is a failure, except these
            if code not in (1001, 4009, 4015) and not self._safe_reconnect_state:
                self.log.warning('[{}] Session unexpectedly terminated. Not reconnecting.'.format(self.channel_id))
                return self.disconnect()

        wait_time = 0

        self.log.info('[{}] {} in {} second{}'.format(self.channel_id, 'Resuming' if self._identified else 'Reconnecting', wait_time, 's' if wait_time != 1 else ''))
        gevent.sleep(wait_time)
        self.connect_and_run()

    def connect(self, channel_id, timeout=10, **kwargs):
        if self.is_dm:
            channel_id = self.server_id

        if not channel_id:
            raise VoiceException('[{}] cannot connect to an empty channel id'.format(self.channel_id), self)

        if self.channel_id == channel_id:
            if self.state == VoiceState.CONNECTED:
                self.log.debug('[{}] Already connected to {}, returning'.format(self.channel_id, self.channel))
                return self
        else:
            if self.state == VoiceState.CONNECTED:
                self.log.debug('[{}] Moving to channel {}'.format(self.channel_id, channel_id))
            else:
                self.log.debug('[{}] Attempting connection to channel id {}'.format(self.channel_id, channel_id))
                self.set_state(VoiceState.AWAITING_ENDPOINT)

        self.set_voice_state(channel_id, **kwargs)

        if not self.state_emitter.once(VoiceState.CONNECTED, timeout=timeout):
            self.disconnect()
            raise VoiceException('Failed to connect to voice', self)
        else:
            return self

    def disconnect(self):
        self._safe_reconnect_state = False
        if self.state == VoiceState.DISCONNECTED:
            return

        self.set_state(VoiceState.DISCONNECTED)

        try:
            self.media.now_playing.source.proc.kill()
        except:
            pass

        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.close()
            self.ws = None

        try:
            self.set_voice_state(None)
        except:
            pass

        if self.udp:
            self.udp.disconnect()

        if self.client.state.voice_clients.get(self.server_id):
            del self.client.state.voice_clients[self.server_id]

        if self.client.state.voice_states.get(self._session_id):
            del self.client.state.voice_states[self._session_id]

        return self.client.gw.events.emit('VoiceDisconnect', self)

    def send_frame(self, *args, **kwargs):
        self.udp.send_frame(*args, **kwargs)

    def increment_timestamp(self, *args, **kwargs):
        self.udp.increment_timestamp(*args, **kwargs)
