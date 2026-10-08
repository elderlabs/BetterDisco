from gevent import sleep as gevent_sleep, spawn as gevent_spawn
from struct import unpack_from as struct_unpack_from
from time import time
try:
    from orjson import JSONDecodeError
except ImportError:
    from json import JSONDecodeError
from collections import namedtuple as namedtuple
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException

try:
    from davey import DaveSession, MediaType as DaveMediaType, ProposalsOperationType as DaveProposalsOperationType, CommitWelcome as DaveCommitWelcome
except ImportError:
    DaveSession = None
    DaveMediaType = None
    DaveProposalsOperationType = None
    DaveCommitWelcome = None

from disco.gateway.encoding import ENCODERS
from disco.gateway.packets import OPCode
from disco.types.base import cached_property
from disco.util.emitter import Emitter, Priority
from disco.util.logging import LoggingClass
from disco.util.websocket import Websocket, get_http_status
from disco.voice.packets import VoiceOPCode
from disco.voice.udp import AudioCodecs, RTPPayloadTypes, UDPVoiceClient, VideoCodecs, OPUS_SILENCE_FRAME


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


VideoStream = namedtuple('VideoStream', [
    'client',
    'user_id',
    'streams',
    'video_ssrc',
    'audio_ssrc',
])


VoiceUser = namedtuple('VoiceUser', [
    'user_id',
    'flags',
    'platform',
])


class VoiceException(Exception):
    def __init__(self, msg, client):
        self.voice_client = client
        super(VoiceException, self).__init__(msg)


class VoiceClient(LoggingClass):
    VOICE_GATEWAY_VERSION = 9

    SUPPORTED_MODES = {
        'aead_aes256_gcm_rtpsize',
        'aead_xchacha20_poly1305_rtpsize',
    }

    def __init__(self, client, server_id, is_dm=False, max_reconnects=5, encoder='json', video_enabled=False):
        super(VoiceClient, self).__init__()

        self.client = client
        self.server_id = server_id
        self.channel_id = None
        self.is_dm = is_dm
        self.encoder = ENCODERS[encoder]  # Discord's erlpack doesn't seem supported here
        self.max_reconnects = max_reconnects
        self.video_enabled = video_enabled
        self.media = None
        self._initial_silence = False

        self.deaf = False
        self.mute = False

        self.proxy = None

        # Set the VoiceClient in the state's voice clients
        self.client.state.voice_clients[self.server_id] = self

        # Bind to some WS packets
        self.packets = Emitter()
        self.packets.on(VoiceOPCode.READY, self.on_voice_ready, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.HEARTBEAT, self.handle_heartbeat, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.SESSION_DESCRIPTION, self.on_voice_sdp, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.SPEAKING, self.on_voice_speaking, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.HEARTBEAT_ACK, self.handle_heartbeat_acknowledge, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.HELLO, self.on_voice_hello, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.RESUMED, self.on_voice_resumed, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.CLIENT_DISCONNECT, self.on_voice_client_disconnect, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.CODECS, self.on_voice_codecs, priority=Priority.BEFORE)
        if self.video_enabled:
            self.packets.on(VoiceOPCode.VIDEO, self.on_video, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.DAVE_TRANSITION_EXECUTE, self.on_dave_transition_execute, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.DAVE_TRANSITION_PREPARE, self.on_dave_transition_prepare, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.DAVE_PREPARE_EPOCH, self.on_dave_prepare_epoch, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.DAVE_MLS_TRANSITION_ANNOUNCE_COMMIT, self.on_dave_mls_transition_announce_commit, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.DAVE_MLS_WELCOME, self.on_dave_mls_welcome, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.DAVE_MLS_EXTERNAL_SENDER, self.on_dave_mls_external_sender, priority=Priority.BEFORE)
        self.packets.on(VoiceOPCode.DAVE_MLS_PROPOSALS, self.on_dave_mls_proposal, priority=Priority.BEFORE)

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
        self.experiments = []
        # self.streams = None
        self.sdp = None
        self.mode = None
        self.udp = None
        self.audio_codec = None
        self.video_codec = None
        self.transport_id = None
        self.keyframe_interval = None
        self.secure_frames_version = None
        self.seq = -1

        # DAVE - E2EE
        self.dave_handler = None
        self.dave_privacy_key = None

        self.max_dave_protocol_version = 1
        self.dave_protocol_version = 0
        self.dave_epoch = 0
        self.dave_identity = 0
        self.dave_credential_type = 1
        self.dave_signature_key = None

        self._dave_transition_id = None
        self.dave_pending_transitions = {}
        self.dave_downgraded = False

        # Websocket connection
        self.ws = None
        self._ws_task = None

        self._session_id = None
        self._reconnects = 0
        self._heartbeat_task = None
        self._reconnect_task = None
        self._heartbeat_acknowledged = True
        self._identified = False
        self._safe_reconnect_state = False
        self._last_http_status = None
        self._creation_time = time()
        self._ws_creation_time = None

        # Latency
        self._last_heartbeat = 0
        self.latency = -1

        # SSRCs
        self.audio_ssrcs = {}
        self.video_ssrcs = {}
        self.rtx_ssrcs = {}

    def __repr__(self):
        return f'<VoiceClient guild_id={self.server_id} channel_id={self.channel_id} endpoint={self.endpoint}>'

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.server_id)

    @cached_property
    def channel(self):
        return self.client.state.channels.get(self.channel_id)

    @property
    def user_id(self):
        return self.client.state.me.id

    def update_media_silence(self):
        if not self.media or self.is_dm or self.channel_id is None:
            return

        guild = self.client.state.guilds.get(self.server_id)
        if not guild:
            return

        for voice_state in guild.voice_states.values():
            if voice_state.channel_id == self.channel_id and voice_state.user_id != self.user_id:
                self.media.set_silenced(False)
                return

        self.media.set_silenced(True)

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
        self.log.info(f'[{self.channel_id or "-"}] state {self.state} -> {state}')
        prev_state = self.state
        self.state = state
        self.state_emitter.emit(state, prev_state)

    def set_endpoint(self, endpoint):
        if self.endpoint == endpoint:
            return

        self.log.info(f'[{self.channel_id}] {self.state} ({endpoint})')

        self.endpoint = endpoint

        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.close()

        self._identified = False

    def set_token(self, token):
        if self.token == token:
            return
        self.token = token
        if not self._identified and not self._reconnect_task and not self._ws_task and not self.ws:
            self._ws_task = gevent_spawn(self.connect_and_run)

    def connect_and_run(self, gateway_url=None):
        if not gateway_url:
            gateway_url = f'wss://{self.endpoint}'
        gateway_url += f'/?v={self.VOICE_GATEWAY_VERSION}&encoding={self.encoder.TYPE}'

        self.ws = Websocket(gateway_url)
        self.ws.emitter.on('on_open', self.on_open, priority=Priority.BEFORE)
        self.ws.emitter.on('on_error', self.on_error, priority=Priority.BEFORE)
        self.ws.emitter.on('on_close', self.on_close, priority=Priority.BEFORE)
        self.ws.emitter.on('on_message', self.on_message, priority=Priority.BEFORE)
        self.ws.run_forever(ping_interval=60, ping_timeout=5)

    def heartbeat_task(self, interval):
        while True:
            if not self._heartbeat_acknowledged:
                self.log.warning(f'[{self.channel_id}] Websocket Received HEARTBEAT without HEARTBEAT_ACK, reconnecting...')
                self._heartbeat_acknowledged = True
                self.ws.close(status=4000)
                self.on_close(0, 'HEARTBEAT failure')
                return
            self._last_heartbeat = time()

            self.send(VoiceOPCode.HEARTBEAT, {'seq_ack': self.seq, 't': int(time())})
            self._heartbeat_acknowledged = False
            gevent_sleep(interval / 1000)

    def handle_heartbeat(self, _):
        self.send(VoiceOPCode.HEARTBEAT, {'seq_ack': self.seq, 't': int(time())})

    def handle_heartbeat_acknowledge(self, _):
        self.log.debug(f'[{self.channel_id}] Received Websocket HEARTBEAT_ACK')
        self._heartbeat_acknowledged = True
        self.latency = self.ws.last_pong_tm and float('{:.2f}'.format((self.ws.last_pong_tm - self.ws.last_ping_tm) * 1000))

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
            self.log.debug(f'[{self.channel_id}] sending OP {op}')
            self.ws.send_text(self.encoder.encode({'op': op, 'd': data}))
        else:
            self.log.debug(f'[{self.channel_id}] dropping, Websocket is closed - OP {op}')

    def send_binary(self, op, data):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.log.debug(f'[{self.channel_id}] sending OP {op}')
            self.ws.send_bytes(bytes([op]) + data)
        else:
            self.log.debug(f'[{self.channel_id}] dropping, Websocket is closed - OP {op}')

    def on_voice_client_disconnect(self, data):
        user_id = int(data['user_id'])
        for ssrc in list(self.audio_ssrcs.keys()):
            if self.audio_ssrcs[ssrc] == user_id:
                if self.udp:
                    self.udp.remove_audio_ssrc(ssrc, user_id)
                del self.audio_ssrcs[ssrc]
                break

        payload = VoiceUser(
            user_id=user_id,
            flags=None,
            platform=None,
        )

        self.client.events.emit('VoiceUserLeave', payload)

    def on_voice_codecs(self, data):
        self.audio_codec = data['audio_codec']
        self.video_codec = data['video_codec']
        if 'media_session_id' in data.keys():
            self.transport_id = data['media_session_id']
        if 'keyframe_interval' in data.keys():
            self.keyframe_interval = data['keyframe_interval']

        # Set the UDP's RTP Audio Header's Payload Type
        # self.udp.set_audio_codec(data['audio_codec'])  # bypass because the audio codec will always be opus

    def on_voice_hello(self, packet):
        self.log.info(f'[{self.channel_id}] Received HELLO payload, starting heartbeater')
        self._heartbeat_task = gevent_spawn(self.heartbeat_task, packet['heartbeat_interval'])
        self.set_state(VoiceState.AUTHENTICATED)

    def on_voice_ready(self, data):
        self.log.info(f'[{self.channel_id}] Received READY payload, RTC connecting')
        self.set_state(VoiceState.CONNECTING)
        self.ssrc = data['ssrc']
        self.audio_ssrcs[self.ssrc] = self.client.state.me.id
        if self.video_enabled:
            self.video_ssrcs[self.ssrc + 1] = self.client.state.me.id
            self.rtx_ssrcs[self.ssrc + 2] = self.client.state.me.id
        self.ip = data['ip']
        self.port = data['port']
        self.enc_modes = data['modes']
        self.experiments = data['experiments']
        self._identified = True

        for mode in self.enc_modes:
            if mode in self.SUPPORTED_MODES:
                self.mode = mode
                self.log.info(f'[{self.channel_id}] Selected mode {mode}')
                break
        else:
            raise Exception('Failed to find a supported voice mode')

        self.log.debug(f'[{self.channel_id}] Attempting IP discovery over UDP to {self.ip}:{self.port}')
        self.udp = UDPVoiceClient(self)
        ip, port = self.udp.connect(self.ip, self.port)

        if not ip:
            self.log.error(f'[{self.channel_id}] Failed to discover bot IP, a network configuration error is likely present.')
            self.disconnect()
            return

        codecs = []

        # Sending discord our available codecs and rtp payload type for it
        for idx, codec in enumerate(AudioCodecs):
            codecs.append({
                'name': codec,
                'payload_type': RTPPayloadTypes.get(codec).value,
                'priority': 1000 + idx,
                'type': 'audio',
            })

        if self.video_enabled:
            for idx, codec in enumerate(VideoCodecs):
                ptype = RTPPayloadTypes.get(codec.lower())
                if ptype:
                    codecs.append({
                        'decode': True,
                        'encode': False,
                        'name': codec,
                        'payload_type': ptype.value,
                        'priority': 1000 * idx,
                        'rtxPayloadType': RTPPayloadTypes.get(codec.lower() + '_rtx').value,
                        'type': 'video',
                    })

        self.log.debug(f'[{self.channel_id}] IP discovery completed ({ip}:{port}), sending SELECT_PROTOCOL')
        self.send(VoiceOPCode.SELECT_PROTOCOL, {
            'protocol': 'udp',
            'data': {
                'address': ip,
                'port': port,
                'mode': self.mode,
            },
            'codecs': codecs,
            'experiments': self.experiments,
        })
        self.send(VoiceOPCode.CLIENT_CONNECT, {
            'audio_ssrc': self.ssrc,
            'video_ssrc': 0,
            'rtx_ssrc': 0,
        })

    def on_voice_resumed(self, _):
        self.log.info(f'[{self.channel_id}] Websocket Resumed')
        self.set_state(VoiceState.CONNECTED)
        self._reconnects = 0
        self._safe_reconnect_state = False
        if self.media:
            self.media.resume()

    def on_voice_sdp(self, sdp):
        self.log.info(f'[{self.channel_id}] Received session description; connected')
        self.mode = sdp['mode']  # UDP-only, does not apply to webRTC
        self.audio_codec = sdp['audio_codec']
        self.transport_id = sdp['media_session_id']  # analytics
        self.secure_frames_version = sdp['secure_frames_version']
        self.dave_protocol_version = sdp['dave_protocol_version']
        if 'sdp' in sdp.keys():
            self.sdp = sdp['sdp']  # webRTC only

        # Set the UDP's RTP Audio Header's Payload Type
        self.udp.set_audio_codec(sdp['audio_codec'])

        if self.video_enabled:
            self.video_codec = sdp['video_codec']
            self.udp.set_video_codec(sdp['video_codec'])
        if 'keyframe_interval' in sdp.keys():
            self.keyframe_interval = sdp['keyframe_interval']

        # Create a secret box for encryption/decryption
        self.udp.setup_encryption(bytes(bytearray(sdp['secret_key'])))  # UDP only

        if sdp['dave_protocol_version']:
            self.dave_reset()

        self.set_state(VoiceState.CONNECTED)

        self._initial_silence = True
        self.update_media_silence()
        self.send_silence()
        self._initial_silence = False
        if self.media and self.media.silenced:
            self.set_speaking(False)

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

        self.client.events.emit('VoiceSpeaking', payload)

    def on_client_connect(self, data):
        user_id = int(data['user_id'])

        payload = VoiceUser(
            user_id=user_id,
            flags=data['flags'],
            platform=None,
        )

        self.client.events.emit('VoiceUserJoin', payload)

    def on_platform(self, data):
        user_id = int(data['user_id'])

        payload = VoiceUser(
            user_id=user_id,
            flags=None,
            platform=data['platform'],
        )

        self.client.events.emit('VoiceUserPlatform', payload)

    def on_video(self, data):
        user_id = int(data['user_id'])
        video_ssrc = data['video_ssrc']

        if video_ssrc:
            self.video_ssrcs[data['video_ssrc']] = user_id
            self.rtx_ssrcs[video_ssrc + 1] = user_id
        else:
            for ssrc, uid in self.video_ssrcs.items():
                if uid == user_id:
                    del self.video_ssrcs[ssrc]
                    break
            for ssrc, uid in self.rtx_ssrcs.items():
                if uid == user_id:
                    del self.rtx_ssrcs[ssrc]
                    break

        payload = VideoStream(
            client=self,
            user_id=user_id,
            streams=data['streams'],
            video_ssrc=video_ssrc,
            audio_ssrc=data['audio_ssrc'],
        )

        if data['video_ssrc']:
            self.client.events.emit('VideoStreamStart', payload)
        else:
            self.client.events.emit('VideoStreamEnd', payload)

    def on_message(self, msg):
        try:
            data = self.encoder.decode(msg)
            self.packets.emit(data['op'], data['d'])
            if 'seq' in data.keys():
                self.seq = data['seq']
        except JSONDecodeError:
            if type(msg) is bytes:  # Hello DAVE
                data = {}
                data['seq'] = int.from_bytes(msg[:2], 'big', signed=False)
                self.seq = data['seq']
                data['op'] = msg[2]  # third byte
                data['d'] = msg[3:]  # everything else after three-byte header
                self.log.debug(f'[{self.channel_id}] Received OP {data["op"]}, SEQ {data["seq"]}')
                self.packets.emit(data['op'], data['d'])

        except Exception as e:
            self.log.error(f'Failed to parse voice gateway message: {e.__class__.__name__} - {e}')

    def on_error(self, error):
        self._last_http_status = get_http_status(error)
        if self._last_http_status:
            return self.log.error(f'[{self.channel_id}] Websocket handshake failed with HTTP status {self._last_http_status}')
        if isinstance(error, WebSocketTimeoutException):
            return self.log.error(f'[{self.channel_id}] Websocket connection has timed out. An upstream connection issue is likely present.')
        if not isinstance(error, WebSocketConnectionClosedException):
            return self.log.error(f'[{self.channel_id}] Websocket received error: {error.__class__.__name__} - {error}')

    def on_open(self):
        self._last_http_status = None
        if self._identified:
            self.send(VoiceOPCode.RESUME, {
                'server_id': self.server_id,
                'channel_id': self.channel_id,
                'session_id': self._session_id,
                'token': self.token,
                'seq_ack': self.seq,
            })
        else:
            self.seq = -1
            self.send(VoiceOPCode.IDENTIFY, {
                'server_id': self.server_id,
                'channel_id': self.channel_id,
                'user_id': self.user_id,
                'session_id': self._session_id,
                'token': self.token,
                'video': self.video_enabled,
                # 'streams': [],
                'max_dave_protocol_version': self.max_dave_protocol_version,
            })

    def reconnect(self, wait_time):
        gevent_sleep(wait_time)
        self._reconnect_task = None
        if self.state == VoiceState.DISCONNECTED:
            return
        self._ws_task = gevent_spawn(self.connect_and_run)

    def on_close(self, code=None, reason=None):
        gevent_sleep(0.001)
        if self.media:
            self.media.pause()
        self.log.info('[{}] Websocket Closed: {}{}({})'.format(self.channel_id, f'[{code}] ' if code else '', f'{reason} ' if reason else '', self._reconnects))

        for handlers in tuple(self.ws.emitter.event_handlers.values()):
            handlers.clear()
        self.ws.emitter = None

        for attr in ('on_close', 'on_cont_message', 'on_data', 'on_error', 'on_message', 'on_open', 'on_ping', 'on_pong', 'on_reconnect'):
            setattr(self.ws, attr, None)

        self.ws.sock = None

        if self._heartbeat_task:
            self.log.debug(f'[{self.channel_id}] killing heartbeater')
            self._heartbeat_task.kill()
            self._heartbeat_task = None

        self.ws = None
        self._ws_task = None
        self._heartbeat_acknowledged = True
        http_status = self._last_http_status
        self._last_http_status = None

        # If we killed the connection, don't try resuming
        if self.state == VoiceState.DISCONNECTED:
            return

        if code in (4004, 4011, 4012, 4014, 4016, 4017, 4021, 4022):
            self.log.warning(f'[{self.channel_id}] Voice gateway session closed with code {code}. Disconnecting without reconnect.')
            return self.disconnect()

        self.set_state(VoiceState.RECONNECTING)
        self._reconnects += 1

        if self.max_reconnects and self._reconnects > self.max_reconnects:
            self.log.error(f'[{self.channel_id}] Failed to reconnect after {self.max_reconnects} attempts, giving up')
            return self.disconnect()

        # Cloudflare can reject the WebSocket handshake with an HTTP status rather than a Discord close code.
        # Retry transient failures using the current voice session first; if the endpoint continues failing,
        # request a fresh voice endpoint.
        if http_status:
            if 500 <= http_status <= 599 or http_status == 408:
                self.log.warning(f'[{self.channel_id}] Voice endpoint returned HTTP {code}. Requesting a fresh voice session.')
                self._identified = False
                self.endpoint = None
                self.token = None
                self.seq = -1
                self.set_state(VoiceState.AWAITING_ENDPOINT)
                self.set_voice_state(self.channel_id, mute=self.mute, deaf=self.deaf, video=self.video_enabled)
                return
            if http_status == 429:  # this should NEVER fire
                self.log.error(f'[{self.channel_id}] Cloudflare sent 429. Give up.')
                return self.disconnect()

        if code is not None and (4000 <= code <= 4022 or code in (1000, 1001)):
            if self.udp and self.udp.connected:
                self.udp.disconnect()

            # 4006 and 4009 invalidate the voice session. Discord requires a new VOICE_STATE_UPDATE
            # and VOICE_SERVER_UPDATE before opening a new voice socket.
            if code in (4006, 4009):
                self.log.warning(f'[{self.channel_id}] Voice session invalidated. Requesting a fresh voice session.')
                self._identified = False
                self.endpoint = None
                self.token = None
                self.seq = -1
                self.set_state(VoiceState.AWAITING_ENDPOINT)
                self.set_voice_state(self.channel_id, mute=self.mute, deaf=self.deaf, video=self.video_enabled)
                return

            # A heartbeat failure is a transport failure.
            # Resume the existing voice session rather than leaving/rejoining the channel.
            if code == 0 and reason and 'HEARTBEAT' in reason:
                self.log.info(f'[{self.channel_id}] Voice heartbeat failed; reconnecting.')

        if self._identified and (self._safe_reconnect_state or code == 4015):
            self.log.info(f'[{self.channel_id}] Attempting Websocket resumption')

        wait_time = (self._reconnects * 5) - 5

        self.log.info('[{}] {} in {} second{}'.format(self.channel_id, 'Resuming' if self._identified else 'Reconnecting', wait_time, 's' if wait_time != 1 else ''))
        if self._reconnect_task:
            self._reconnect_task.kill()
        self._reconnect_task = gevent_spawn(self.reconnect, wait_time)

    def connect(self, channel_id, timeout=10, **kwargs):
        if self.is_dm:
            channel_id = self.server_id

        if not channel_id:
            raise VoiceException(f'[{self.channel_id}] cannot connect to an empty channel id', self)

        if self.channel_id == channel_id:
            if self.state == VoiceState.CONNECTED:
                self.log.info(f'[{self.channel_id}] Already connected to {self.channel}, returning')
                return self
        else:
            if self.state == VoiceState.CONNECTED:
                self.log.info(f'[{self.channel_id}] Moving to channel {channel_id}')
            else:
                self.log.info(f'[{self.channel_id or "-"}] Attempting connection to channel id {channel_id}')
                self.set_state(VoiceState.AWAITING_ENDPOINT)

        self.set_voice_state(channel_id, **kwargs)

        if not self.state_emitter.once(VoiceState.CONNECTED, timeout=timeout):
            self.disconnect()
            self.log.error(f'[{self.channel_id}] Failed to connect to voice')
        else:
            self._ws_creation_time = time()
            return self

    def disconnect(self, reconnect=False):
        if reconnect:
            self._safe_reconnect_state = True
        else:
            self._safe_reconnect_state = False

        if self.state == VoiceState.DISCONNECTED:
            return

        if self._reconnect_task:
            self._reconnect_task.kill()
            self._reconnect_task = None

        self.set_state(VoiceState.DISCONNECTED)

        if not reconnect:
            try:
                self.media.now_playing.source.proc.kill()
                self.media.now_playing.source = None
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

        if not reconnect:
            if self.client.state.voice_clients.get(self.server_id):
                del self.client.state.voice_clients[self.server_id]

            if self.client.state.voice_states.get(self._session_id):
                del self.client.state.voice_states[self._session_id]

        return self.client.events.emit('VoiceDisconnect', self)

    def send_silence(self, frames=5):
        if self.state != VoiceState.CONNECTED or not self.udp:
            return

        self.set_speaking(True)
        for _ in range(frames):
            self.udp.send_silence(1)
            gevent_sleep(0.02)

    def send_frame(self, frame, *args, **kwargs):
        if self.dave_handler and not self.dave_downgraded:
            try:
                frame = self.dave_handler.encrypt_opus(frame)
            except ValueError:
                pass
        self.udp.send_frame(frame, *args, **kwargs)

    def decrypt_voice_frame(self, user_id, frame):
        if not self.dave_handler or not user_id or frame == OPUS_SILENCE_FRAME or DaveMediaType is None:
            return frame

        can_decrypt = (self.dave_protocol_version and not self.dave_downgraded and self.dave_handler.ready) or \
                      (self.dave_handler.ready and self.dave_handler.can_passthrough(user_id))
        if not can_decrypt:
            return frame

        return self.dave_handler.decrypt(user_id, DaveMediaType.audio, frame)

    def decrypt_video_frame(self, user_id, frame):
        if not self.dave_handler or not user_id or DaveMediaType is None:
            return frame

        can_decrypt = (self.dave_protocol_version and not self.dave_downgraded and self.dave_handler.ready) or \
                      (self.dave_handler.ready and self.dave_handler.can_passthrough(user_id))
        if not can_decrypt:
            return frame

        return self.dave_handler.decrypt(user_id, DaveMediaType.video, frame)

    def increment_timestamp(self, *args, **kwargs):
        self.udp.increment_timestamp(*args, **kwargs)

    # Discord End-to-End Encryption Protocol Support (DAVE); RFC9420
    def on_dave_transition_execute(self, transition_id):  # OP: 22
        if isinstance(transition_id, dict):
            transition_id = transition_id['transition_id']
        self.log.info(f'[{self.channel_id}] DAVE Execute Transition {transition_id}')
        if transition_id not in self.dave_pending_transitions.keys():
            return
        if transition_id != self.dave_protocol_version and not self.dave_protocol_version:
            self.dave_downgraded = True  # connection is downgraded and unchanged
            self.log.info(f'[{self.channel_id}] DAVE Execute Transition {transition_id} downgraded')
        elif transition_id and self.dave_downgraded:
            self.dave_downgraded = False
            if self.dave_handler:
                self.dave_handler.set_passthrough_mode(True, 10)
            self.log.info(f'[{self.channel_id}] DAVE Execute Transition {transition_id} upgraded')
        self.log.info(f'[{self.channel_id}] DAVE Execute Transition {transition_id} complete')

    # received on connection downgrade
    def on_dave_transition_prepare(self, data):  # OP: 21
        self.log.info(f'[{self.channel_id}] DAVE Preparing Transition')
        self.dave_protocol_version = data['protocol_version']
        self._dave_transition_id = data['transition_id']
        self.dave_pending_transitions[self._dave_transition_id] = self.dave_protocol_version

        if self._dave_transition_id == 0:
            self.on_dave_transition_execute(self._dave_transition_id)
        elif not self.dave_protocol_version and self.dave_handler:
            self.dave_handler.set_passthrough_mode(True, 120)

        self.dave_transition_ready(self._dave_transition_id)

    def on_dave_prepare_epoch(self, data):  # OP: 24
        self.log.info(f'[{self.channel_id}] DAVE Preparing EPOCH {data["epoch"]}')
        if data['epoch'] == 1:
            self.dave_protocol_version = data['protocol_version']
            self.dave_reset()

    # binary received from welcome
    def on_dave_mls_transition_announce_commit(self, data):  # OP: 29
        transition_id = struct_unpack_from('>H', data)[0]
        try:
            self.dave_handler.process_commit(data[2:])
            if transition_id != 0:
                self.dave_pending_transitions[transition_id] = self.dave_protocol_version
                self.dave_transition_ready(transition_id)
            self.log.info(f'[{self.channel_id}] DAVE MLS Commit transition {transition_id} processed')
        except:
            self.dave_mls_commit_welcome_invalid(transition_id)

    def on_dave_mls_welcome(self, data):  # OP: 30
        transition_id = struct_unpack_from('>H', data)[0]
        try:
            self.dave_handler.process_welcome(data[2:])
            if transition_id != 0:
                self.dave_pending_transitions[transition_id] = self.dave_protocol_version
                self.dave_transition_ready(transition_id)
            self.log.info(f'[{self.channel_id}] DAVE MLS Welcome transition {transition_id} processed')
        except:
            self.dave_mls_commit_welcome_invalid(transition_id)

    # contains creds and key to join an MLS group in binary
    def on_dave_mls_external_sender(self, data):  # OP: 25
        self.dave_handler.set_external_sender(data)
        self.log.info(f'[{self.channel_id}] DAVE MLS External Sender set')

    # contains list of proposals to be added or removed
    def on_dave_mls_proposal(self, data):  # OP: 27
        result = self.dave_handler.process_proposals(DaveProposalsOperationType.append if data[0] == 0 else DaveProposalsOperationType.revoke, data[1:])
        if isinstance(result, DaveCommitWelcome):
            self.dave_mls_commit_welcome(result)
        self.log.info(f'[{self.channel_id}] DAVE MLS Proposals processed')

    def dave_transition_ready(self, transition_id):  # OP: 23
        self.log.info(f'[{self.channel_id}] DAVE Transition {transition_id} ready')
        self.send(VoiceOPCode.DAVE_TRANSITION_READY, {'transition_id': transition_id,})

    # sends key package in binary
    def dave_mls_key_package(self):  # OP: 26
        self.log.info(f'[{self.channel_id}] DAVE MLS Key Package sending')
        self.send_binary(VoiceOPCode.DAVE_MLS_KEY_PACKAGE, self.dave_handler.get_serialized_key_package())

    # sends commit and welcome on new user join
    def dave_mls_commit_welcome(self, data):  # OP: 28
        self.send_binary(VoiceOPCode.DAVE_MLS_WELCOME_COMMIT, data.commit + data.welcome if data.welcome else data.commit)

    def dave_mls_commit_welcome_invalid(self, transition_id):  # OP: 31
        self.log.info(f'[{self.channel_id}] DAVE MLS Key Commit Welcome transition {transition_id} invalid')
        self.send(VoiceOPCode.DAVE_MLS_WELCOME_INVALID_COMMIT, {'transition_id': transition_id,})
        self.dave_reset()

    def dave_reset(self):
        if self.dave_protocol_version:
            if self.dave_handler:
                self.log.info(f'[{self.channel_id}] DAVE reinitializing')
                self.dave_handler.reinit(self.dave_protocol_version, self.client.state.me.id, self.channel_id)
            else:
                self.log.info(f'[{self.channel_id}] DAVE initializing')
                self.dave_handler = DaveSession(self.dave_protocol_version, self.client.state.me.id, self.channel_id)
            self.dave_mls_key_package()
        elif self.dave_handler:
            self.log.info(f'[{self.channel_id}] DAVE shutting down')
            self.dave_handler.reset()
            self.dave_handler.set_passthrough_mode(True, 10)
