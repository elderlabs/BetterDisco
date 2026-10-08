from gevent import sleep as gevent_sleep, spawn as gevent_spawn
from gevent.event import Event as GeventEvent
from platform import system as platform_system
from sys import version_info as sys_version_info, modules as sys_modules
from time import time, perf_counter_ns as time_perf_counter_ns
from websocket import ABNF, WebSocketConnectionClosedException, WebSocketTimeoutException

from disco.gateway.packets import OPCode, RECV, SEND
from disco.gateway.events import GatewayEvent
from disco.gateway.encoding import ENCODERS
from disco.util.websocket import Websocket, get_http_status
from disco.util.emitter import Priority
from disco.util.logging import LoggingClass
from disco.util.limiter import SimpleLimiter


class GatewayClient(LoggingClass):
    def __init__(self, client, max_reconnects=5, encoder='json', zlib_stream_enabled=False, zstd_stream_enabled=False, ipc=None, ignored_events=[], subscribed_events=[]):
        super(GatewayClient, self).__init__()
        self.client = client
        self.max_reconnects = max_reconnects
        self.encoder = ENCODERS[encoder]
        self.zlib_stream_enabled = zlib_stream_enabled
        self.zstd_stream_enabled = zstd_stream_enabled

        if sys_version_info >= (3, 14):
            global ZstdDecompressor; from compression.zstd import ZstdDecompressor
        else:
            try:
                global ZstdDecompressor; from zstandard import ZstdDecompressor
            except ImportError:
                self.zstd_stream_enabled = False

        try:
            global zlib_decompress
            global zlib_decompressobj
            from isal.isal_zlib import decompress as zlib_decompress, decompressobj as zlib_decompressobj
        except ImportError:
            try:
                from zlib import decompress as zlib_decompress, decompressobj as zlib_decompressobj
            except ImportError:
                self.zlib_stream_enabled = False

        self.ignored_events = ignored_events
        self.subscribed_events = subscribed_events
        self.events = client.events
        self.packets = client.packets

        # IPC for shards
        if ipc:
            self.shards = ipc.get_shards()
            self.ipc = ipc

        self.limiter = SimpleLimiter(120, 60)

        # Create emitter and bind to gateway payloads
        self.packets.on((RECV, OPCode.DISPATCH), self.handle_dispatch, priority=Priority.BEFORE)
        self.packets.on((RECV, OPCode.HEARTBEAT), self.handle_heartbeat, priority=Priority.BEFORE)
        self.packets.on((RECV, OPCode.HEARTBEAT_ACK), self.handle_heartbeat_acknowledge, priority=Priority.BEFORE)
        self.packets.on((RECV, OPCode.RECONNECT), self.handle_reconnect, priority=Priority.BEFORE)
        self.packets.on((RECV, OPCode.INVALID_SESSION), self.handle_invalid_session, priority=Priority.BEFORE)
        self.packets.on((RECV, OPCode.HELLO), self.handle_hello, priority=Priority.BEFORE)

        # Bind to ready payload
        self.events.on('Ready', self.on_ready)
        self.events.on('Resumed', self.on_resumed)

        # Websocket connection
        self.ws = None
        self.ws_task = None
        self._reconnect_task = None
        self.ws_event = GeventEvent()
        self._zlib = None
        self._zstd = None
        self._buffer = None

        # State
        self.seq = 0
        self.session_id = None
        self.reconnects = 0
        self.shutting_down = False
        self.replaying = False
        self.replayed_events = 0
        self.last_conn_state = None
        self.resuming = False
        self._last_http_status = None

        # Cached gateway URL
        self._cached_gateway_url = None

        # Heartbeat
        self._heartbeat_task = None
        self._heartbeat_acknowledged = True

        # Latency
        self._last_heartbeat = 0
        self.latency = -1

    def __repr__(self):
        return f'<GatewayClient shard_id={self.client.config.shard_id} endpoint={self._cached_gateway_url}>'

    def send(self, op, data):
        if self.ws and not self.ws.is_closed:
            self.limiter.check()
            return self._send(op, data)

    def _send(self, op, data):
        self.log.debug(f'GatewayClient.send OP: {op}')
        self.packets.emit((SEND, op), data)
        self.ws.send(self.encoder.encode({
            'op': op,
            'd': data,
        }), self.encoder.OPCODE)

    def heartbeat_task(self, interval):
        while True:
            if not self._heartbeat_acknowledged:
                self.log.warning('Received HEARTBEAT without HEARTBEAT_ACK, forcing a fresh reconnect')
                self.last_conn_state = 'HEARTBEAT'
                self._heartbeat_acknowledged = True
                self.ws.close(status=1000)
                # self.client.gw.on_close(0, 'HEARTBEAT failure')
                return
            self._last_heartbeat = time()

            self.handle_heartbeat()
            self._heartbeat_acknowledged = False
            gevent_sleep(interval / 1000)

    # overridable for additional logic
    def pre_dispatch(self, packet):
        return packet

    def handle_dispatch(self, packet):
        try:
            packet['d']['timestamp_ns'] = time_perf_counter_ns()
            obj = GatewayEvent.from_dispatch(self.client, packet)
        except Exception as e:
            if self.client.config.log_unknown_events:
                return self.log.warning(f'{e.__class__.__name__}: {e}')  # this probably isn't perfect
            return

        self.log.debug(f'GatewayClient.handle_dispatch {obj.__class__.__name__}')
        self.client.events.emit(obj.__class__.__name__, obj)
        if self.replaying:
            self.replayed_events += 1

    def handle_heartbeat(self, _=None):
        try:
            self._send(OPCode.HEARTBEAT, self.seq)
        except WebSocketConnectionClosedException:
            pass
        except Exception as e:
            raise e

    def handle_heartbeat_acknowledge(self, _):
        self.log.debug('Received HEARTBEAT_ACK')
        self._heartbeat_acknowledged = True
        self.latency = self.ws.last_pong_tm and float('{:.2f}'.format((self.ws.last_pong_tm - self.ws.last_ping_tm) * 1000))

    def handle_reconnect(self, _):
        self.log.warning('Received RECONNECT request; resuming')
        self.last_conn_state = 'RECONNECT'
        self.resuming = True
        self.ws.close(status=4000)

    def handle_invalid_session(self, packet):
        if packet.get('d'):
            self.log.warning('Received INVALID_SESSION, resuming')
            self.resuming = True
        else:
            self.log.warning('Received INVALID_SESSION, forcing a fresh reconnect')
            self.session_id = None
            self.seq = 0
            self.resuming = False
        self.last_conn_state = 'INVALID_SESSION'
        self.ws.close(status=4000)

    def handle_hello(self, packet):
        self.replayed_events = 0
        self.log.info('Received HELLO, starting heartbeater...')
        self._heartbeat_task = gevent_spawn(self.heartbeat_task, packet['d']['heartbeat_interval'])

    def on_ready(self, ready):
        self.log.info('Received READY')
        self.session_id = ready.session_id
        self._cached_gateway_url = ready.resume_gateway_url
        self.reconnects = 0
        for vc in self.client.state.voice_clients.values():
            if vc.channel_id and not vc._identified:
                vc.set_voice_state(vc.channel_id, mute=vc.mute, deaf=vc.deaf, video=vc.video_enabled)

    def on_resumed(self, _):
        self.log.info(f'RESUME completed, replayed {self.replayed_events} event{"s" if self.replayed_events > 1 else ""}')
        self.reconnects = 0
        self.replaying = False
        self.resuming = False
        for vc in self.client.state.voice_clients.values():
            if vc.channel_id and not vc._identified:
                vc.set_voice_state(vc.channel_id, mute=vc.mute, deaf=vc.deaf, video=vc.video_enabled)

    def connect_and_run(self, gateway_url=None):
        if not gateway_url:
            if not self._cached_gateway_url:
                try:
                    self._cached_gateway_url = self.client.api.gateway_get()['url']
                except:
                    self._cached_gateway_url = self.client.config.gateway_url.replace('https://', 'wss://')

            gateway_url = self._cached_gateway_url

        gateway_url += f'/?v={self.client.config.gateway_version}&encoding={self.encoder.TYPE}'

        if self.zstd_stream_enabled and ('zstandard' in sys_modules.keys() or '_compression' in sys_modules.keys() and sys_version_info >= (3, 14)):
            gateway_url += '&compress=zstd-stream'
        elif self.zlib_stream_enabled:  # transport compression may not benefit ETF?
            gateway_url += '&compress=zlib-stream'

        self.log.info(f'Opening websocket connection to `{gateway_url}`')
        self.ws = Websocket(gateway_url)
        self.ws.emitter.on('on_open', self.on_open, priority=Priority.BEFORE)
        self.ws.emitter.on('on_error', self.on_error, priority=Priority.BEFORE)
        self.ws.emitter.on('on_close', self.on_close, priority=Priority.BEFORE)
        self.ws.emitter.on('on_message', self.on_message, priority=Priority.BEFORE)

        self.ws.run_forever(ping_interval=60, ping_timeout=5)

    def on_message(self, msg):
        if self.zstd_stream_enabled:
            msg = self._zstd.decompress(msg)

            if self.encoder.OPCODE == ABNF.OPCODE_TEXT:
                msg = str(msg, 'utf-8')

        elif self.zlib_stream_enabled:
            if not self._buffer:
                self._buffer = bytearray()

            self._buffer.extend(msg)

            if len(msg) < 4:
                return

            if msg[-4:] != b'\x00\x00\xff\xff':
                return

            msg = self._zlib.decompress(self._buffer)
            # If encoder is text based, decode the data as utf-8
            if self.encoder.OPCODE == ABNF.OPCODE_TEXT:
                msg = str(msg, 'utf-8')
            self._buffer = None
        else:
            # Detect zlib, decompress
            is_erlpack = (msg[0] == 131)
            if msg[0] != '{' and not is_erlpack:
                msg = str(zlib_decompress(msg, 15, 10490000), 'utf-8')  # 10490000 = 10MB

        try:
            data = self.encoder.decode(msg)
        except Exception as e:
            self.log.exception(f'Failed to parse gateway message: {e.__class__.__name__} - {e}')
            return

        # Update sequence
        if data['s'] and data['s'] > self.seq:
            self.seq = data['s']

        if data['op'] in (OPCode.DISPATCH, OPCode.VOICE_STATE_UPDATE) and ((self.ignored_events and data['t'] in self.ignored_events) or (self.subscribed_events and data['t'] not in self.subscribed_events) or not self.pre_dispatch(data)):
            return
        # Emit packet
        self.packets.emit((RECV, data['op']), data)

    def on_error(self, error):
        if isinstance(error, KeyboardInterrupt):
            self.shutting_down = True
            self.ws_event.set()
        self.resuming = True  # ideally this should be fine
        self._last_http_status = get_http_status(error)
        if self._last_http_status:
            return self.log.error(f'Websocket handshake failed with HTTP status {self._last_http_status}')  # things are NOT fine... 🔥
        if isinstance(error, WebSocketTimeoutException):
            return self.log.error('Websocket connection has timed out. An upstream connection issue is likely present.')
        if not isinstance(error, WebSocketConnectionClosedException):
            return self.log.error(f'Websocket received error: {error.__class__.__name__} - {error}')
        return self.log.error(f'Websocket received error: {error.__class__.__name__} - {error}')

    def on_open(self):
        self._last_http_status = None
        self.ws.is_closed = False
        if self.zstd_stream_enabled:
            if sys_version_info >= (3, 14):
                self._zstd = ZstdDecompressor().decompress()
            else:
                self._zstd = ZstdDecompressor().decompressobj()
        if self.zlib_stream_enabled and not self._zstd:
            self._zlib = zlib_decompressobj()

        if self.seq and self.session_id:
            self.log.info(f'Websocket Opened: attempting resume with SID: {self.session_id} SEQ: {self.seq}')
            self.replaying = True
            self.send(OPCode.RESUME, {
                'token': self.client.config.token,
                'session_id': self.session_id,
                'seq': self.seq,
            })
        else:
            self.seq = 0
            self.log.info('Websocket Opened: sending identify payload')
            self.send(OPCode.IDENTIFY, {
                'token': self.client.config.token,
                'compress': self.encoder.TYPE == 'json' and True or False,  # json-only, payload compression
                'large_threshold': 250,
                'intents': self.client.config.intents,
                'shard': [
                    int(self.client.config.shard_id),
                    int(self.client.config.shard_count),
                ],
                'properties': {
                    'os': platform_system(),
                    'browser': 'disco',
                    'device': 'disco',
                },
            })

    def reconnect(self, wait_time):
        gevent_sleep(wait_time)
        self._reconnect_task = None
        if self.shutting_down:
            return
        self.ws_task = gevent_spawn(self.connect_and_run, self._cached_gateway_url)

    def on_close(self, code=None, reason=None):
        # Make sure we clean up any old data
        self.ws.is_closed = True

        for handlers in tuple(self.ws.emitter.event_handlers.values()):
            handlers.clear()
        self.ws.emitter = None

        for attr in ('on_close', 'on_cont_message', 'on_data', 'on_error', 'on_message', 'on_open', 'on_ping', 'on_pong', 'on_reconnect'):
            setattr(self.ws, attr, None)

        self.ws.sock = None
        self.ws = None
        self.ws_task = None
        self._buffer = None
        self._zlib = None
        self._zstd = None

        # Kill heartbeater, a reconnect/resume will trigger a HELLO which will respawn it
        if self._heartbeat_task:
            self.log.debug('Websocket Closed: killing heartbeater')
            self._heartbeat_task.kill()
            self._heartbeat_task = None

        # If we're quitting, just break out of here
        if self.shutting_down:
            if self._reconnect_task:
                self._reconnect_task.kill()
                self._reconnect_task = None
            self.log.info('Websocket Closed: shutting down')
            return

        self.replaying = False
        self._heartbeat_acknowledged = True

        # Track reconnect attempts
        if reason:
            self.last_conn_state = reason
        http_status = self._last_http_status
        self._last_http_status = None
        self.reconnects += 1
        self.log.info('Websocket Closed: {}{}{}({})'.format(f'[{code}] ' if code else '', f'[{http_status}] ' if http_status else '', f'{reason} ' if reason else '', self.reconnects))

        if self.max_reconnects and self.reconnects > self.max_reconnects:
            return self.log.error(f'Failed to reconnect after {self.max_reconnects} attempts, giving up')

        # Close codes that explicitly prohibit reconnecting.
        if (code and code in (4004, 4010, 4011, 4012, 4013, 4014)) or (http_status and http_status == 429):
            reason = 'Unknown.'
            if code:
                reason = {
                    4004: 'Invalid token.',
                    4010: 'Invalid shard ID.',
                    4011: 'Sharding required.' if self.client.config.shard_count == 1 else 'Further sharding required.',
                    4012: 'Invalid API version.',
                    4013: 'Invalid intents.',
                    4014: 'Disallowed intents. (check the Discord Developer dashboard settings)',
                }[code]
            if http_status:  # this should NEVER fire
                reason = 'Cloudflare sent 429. Give up.'
            self.shutting_down = True
            self.ws_event.set()
            self.log.error(f'Unable to continue, shutting down. Reason: {reason}')
            from sys import exit as sys_exit
            return sys_exit(1)

        # A failed HTTP handshake is not a Discord Gateway close code. Treat upstream 5xx responses as
        # a failed resume and fall back to the initial Gateway URL so Discord can issue a new session.
        # A 408 is also a transient HTTP failure and must not be mistaken for a Discord close code.
        # 1000, 1001, 4007, and 4009 require a new Gateway session rather than resuming the old one.
        # A connection without a close code should be resumable.
        if (http_status and (500 <= http_status <= 599 or http_status == 408)) or (code in (1000, 1001, 4007, 4009) or (not code and not self.resuming)):
            self._cached_gateway_url = None
            self.session_id = None
            self.seq = 0
            self.resuming = False

        # A Gateway reconnect does not imply a fresh voice session when the existing voice socket remains identified.
        # VoiceClient will request a new VOICE_STATE_UPDATE if it has lost its own session.
        if not self.resuming:
            for vc in self.client.state.voice_clients.values():
                vc._safe_reconnect_state = True

        wait_time = (self.reconnects - 1) * 5 if self.reconnects < 6 else 30
        self.log.info(f'{"Resuming" if self.session_id else "Reconnecting"} in {wait_time} seconds')
        if self._reconnect_task:
            self._reconnect_task.kill()
        self._reconnect_task = gevent_spawn(self.reconnect, wait_time)

    def run(self):
        self.ws_task = gevent_spawn(self.connect_and_run)
        self.ws_event.wait()

    def request_guild_members(self, guild_id, query=None, limit=0, presences=False):
        """
        Request a batch of Guild members from Discord. Generally this function
        can be called when initially loading Guilds to fill the local member state.
        """
        self.send(OPCode.REQUEST_GUILD_MEMBERS, {
            'guild_id': guild_id,
            'limit': limit,
            'presences': presences,
            'query': query or '',
        })

    def request_guild_members_by_id(self, guild_id, user_ids, limit=0, presences=False):
        """
        Request a batch of Guild members from Discord by their snowflake(s).
        """
        self.send(OPCode.REQUEST_GUILD_MEMBERS, {
            'guild_id': guild_id,
            'limit': limit,
            'presences': presences,
            'user_ids': user_ids,
        })
