import gevent
import platform
import time
import zlib

from websocket import ABNF, WebSocketConnectionClosedException, WebSocketTimeoutException

from disco.gateway.packets import OPCode, RECV, SEND
from disco.gateway.events import GatewayEvent
from disco.gateway.encoding import ENCODERS
from disco.util.websocket import Websocket
from disco.util.logging import LoggingClass
from disco.util.limiter import SimpleLimiter

TEN_MEGABYTES = 10490000
ZLIB_SUFFIX = b'\x00\x00\xff\xff'


class GatewayClient(LoggingClass):
    GATEWAY_VERSION = 9

    def __init__(self, client, max_reconnects=5, encoder='json', zlib_stream_enabled=True, ipc=None):
        super(GatewayClient, self).__init__()
        self.client = client
        self.max_reconnects = max_reconnects
        self.encoder = ENCODERS[encoder]
        self.zlib_stream_enabled = zlib_stream_enabled

        self.events = client.events
        self.packets = client.packets

        # IPC for shards
        if ipc:
            self.shards = ipc.get_shards()
            self.ipc = ipc

        # Is actually 60, but 120 allows a buffer
        self.limiter = SimpleLimiter(60, 130)

        # Create emitter and bind to gateway payloads
        self.packets.on((RECV, OPCode.DISPATCH), self.handle_dispatch)
        self.packets.on((RECV, OPCode.HEARTBEAT), self.handle_heartbeat)
        self.packets.on((RECV, OPCode.HEARTBEAT_ACK), self.handle_heartbeat_acknowledge)
        self.packets.on((RECV, OPCode.RECONNECT), self.handle_reconnect)
        self.packets.on((RECV, OPCode.INVALID_SESSION), self.handle_invalid_session)
        self.packets.on((RECV, OPCode.HELLO), self.handle_hello)

        # Bind to ready payload
        self.events.on('Ready', self.on_ready)
        self.events.on('Resumed', self.on_resumed)

        # Websocket connection
        self.ws = None
        self.ws_event = gevent.event.Event()
        self._zlib = None
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

        # Cached gateway URL
        self._cached_gateway_url = None

        # Heartbeat
        self._heartbeat_task = None
        self._heartbeat_acknowledged = True

        # Latency
        self._last_heartbeat = 0
        self.latency = -1

    def send(self, op, data):
        self.limiter.check()
        return self._send(op, data)

    def _send(self, op, data):
        self.log.debug('GatewayClient.send %s', op)
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
                self.client.gw.on_close(0, 'HEARTBEAT failure')
                return
            self._last_heartbeat = time.perf_counter()

            self._send(OPCode.HEARTBEAT, self.seq)
            self._heartbeat_acknowledged = False
            gevent.sleep(interval / 1000)

    def handle_dispatch(self, packet):
        try:
            obj = GatewayEvent.from_dispatch(self.client, packet)
        except Exception as e:
            if self.client.config.log_unknown_events:
                return self.log.warning(e)  # this probably isn't perfect
            return

        self.log.debug(f'GatewayClient.handle_dispatch {obj.__class__.__name__}')
        self.client.events.emit(obj.__class__.__name__, obj)
        if self.replaying:
            self.replayed_events += 1

    def handle_heartbeat(self, _):
        self._send(OPCode.HEARTBEAT, self.seq)

    def handle_heartbeat_acknowledge(self, _):
        self.log.debug('Received HEARTBEAT_ACK')
        self._heartbeat_acknowledged = True
        self.latency = float('{:.2f}'.format((time.perf_counter() - self._last_heartbeat) * 1000))

    def handle_reconnect(self, _):
        self.log.warning('Received RECONNECT request; resuming')
        self.last_conn_state = 'RECONNECT'
        self.resuming = True
        self.ws.close(status=4000)

    def handle_invalid_session(self, _):
        self.log.warning('Received INVALID_SESSION, forcing a fresh reconnect')
        self.last_conn_state = 'INVALID_SESSION'
        self.session_id = None
        self.ws.close(status=4000)

    def handle_hello(self, packet):
        self.replayed_events = 0
        self.log.info('Received HELLO, starting heartbeater...')
        self._heartbeat_task = gevent.spawn(self.heartbeat_task, packet['d']['heartbeat_interval'])

    def on_ready(self, ready):
        self.log.info('Received READY')
        self.session_id = ready.session_id
        self._cached_gateway_url = ready.resume_gateway_url
        self.reconnects = 0

    def on_resumed(self, _):
        self.log.info(f'RESUME completed, replayed {self.replayed_events} events')
        self.reconnects = 0
        self.replaying = False
        self.resuming = False

    def connect_and_run(self, gateway_url=None):
        if not gateway_url:
            if not self._cached_gateway_url:
                self._cached_gateway_url = self.client.api.gateway_get()['url']

            gateway_url = self._cached_gateway_url

        gateway_url += f'?v={self.GATEWAY_VERSION}&encoding={self.encoder.TYPE}'

        if self.zlib_stream_enabled:
            gateway_url += '&compress=zlib-stream'

        self.log.info(f'Opening websocket connection to `{gateway_url}`')
        self.ws = Websocket(gateway_url)
        self.ws.emitter.on('on_open', self.on_open)
        self.ws.emitter.on('on_error', self.on_error)
        self.ws.emitter.on('on_close', self.on_close)
        self.ws.emitter.on('on_message', self.on_message)

        self.ws.run_forever()

    def on_message(self, msg):
        if self.zlib_stream_enabled:
            if not self._buffer:
                self._buffer = bytearray()

            self._buffer.extend(msg)

            if len(msg) < 4:
                return

            if msg[-4:] != ZLIB_SUFFIX:
                return

            msg = self._zlib.decompress(self._buffer)
            # If encoder is text based, decode the data as utf-8
            if self.encoder.OPCODE == ABNF.OPCODE_TEXT:
                msg = str(msg, 'utf=8')
            self._buffer = None
        else:
            # Detect zlib, decompress
            is_erlpack = (msg[0] == 131)
            if msg[0] != '{' and not is_erlpack:
                msg = str(zlib.decompress(msg, 15, TEN_MEGABYTES), 'utf=8')

        try:
            data = self.encoder.decode(msg)
        except Exception:
            self.log.exception('Failed to parse gateway message: ')
            return

        # Update sequence
        if data['s'] and data['s'] > self.seq:
            self.seq = data['s']

        # Emit packet
        self.packets.emit((RECV, data['op']), data)

    def on_error(self, error):
        if isinstance(error, KeyboardInterrupt):
            self.shutting_down = True
            self.ws_event.set()
        self.resuming = True  # ideally this should be fine
        if isinstance(error, WebSocketTimeoutException):
            return self.log.error('Websocket connection has timed out. An upstream connection issue is likely present.')
        if not isinstance(error, WebSocketConnectionClosedException):
            return self.log.error(f'WS received error: {error}')
        else:
            return self.log.warning(f'WS received error: {error}')

    def on_open(self):
        if self.zlib_stream_enabled:
            self._zlib = zlib.decompressobj()

        if self.seq and self.session_id:
            self.log.info(f'WS Opened: attempting resume with SID: {self.session_id} SEQ: {self.seq}')
            self.replaying = True
            self.send(OPCode.RESUME, {
                'token': self.client.config.token,
                'session_id': self.session_id,
                'seq': self.seq,
            })
        else:
            self.log.info('WS Opened: sending identify payload')
            self.send(OPCode.IDENTIFY, {
                'token': self.client.config.token,
                'compress': True,
                'large_threshold': 250,
                'intents': self.client.config.intents,
                'shard': [
                    int(self.client.config.shard_id),
                    int(self.client.config.shard_count),
                ],
                'properties': {
                    'os': platform.system(),
                    'browser': 'disco',
                    'device': 'disco',
                },
            })

    def on_close(self, code=None, reason=None):
        # Make sure we clean up any old data
        self._buffer = None

        # Kill heartbeater, a reconnect/resume will trigger a HELLO which will respawn it
        if self._heartbeat_task:
            self.log.info('WS Closed: killing heartbeater')
            self._heartbeat_task.kill()
            self._heartbeat_task = None

        # If we're quitting, just break out of here
        if self.shutting_down:
            self.log.info('WS Closed: shutting down')
            return

        self.replaying = False
        self._heartbeat_acknowledged = True

        # Track reconnect attempts
        if reason:
            self.last_conn_state = reason
        self.reconnects += 1
        self.log.info('WS Closed: {}{}({})'.format(f'[{code}] ' if code else '', f'{reason} ' if reason else '', self.reconnects))

        if self.max_reconnects and self.reconnects > self.max_reconnects:
            return self.log.error(f'Failed to reconnect after {self.max_reconnects} attempts, giving up')

        # Allows us to resume VC clients if our GW is lost at the same time
        if not self.resuming:
            for vc in self.client.state.voice_clients.values():
                vc._safe_reconnect_state = True
        # Don't resume for these error codes
        if code and (4000 < code <= 4010 or code in (1000, 1001)) or (not code and not self.resuming):
            self.session_id = None
        # 4004 and all codes above 4009 are not resumable
        if code and (code == 4004 or code >= 4010):
            reason = 'Unknown.'
            if code == 4004:
                reason = 'Invalid token.'
            if code == 4010:
                reason = 'Invalid shard ID.'
            if code == 4011:
                reason = 'Sharding required.' if self.client.config.shard_count == 1 else 'Further sharding required.'
            if code == 4012:
                reason = 'Invalid API version.'
            if code == 4013:
                reason = 'Invalid intents.'
            if code == 4014:
                reason = 'Unauthorized intents. (check the Discord Developer dashboard settings)'
            self.log.error(f'Unable to continue, shutting down. Reason: {reason}')
            import sys
            return sys.exit(1)

        wait_time = (self.reconnects - 1) * 5 if self.reconnects < 6 else 30
        self.log.info(f'Will attempt to {"resume" if self.session_id else "reconnect"} after {wait_time} seconds')
        gevent.sleep(wait_time)

        # Reconnect
        self.connect_and_run(self._cached_gateway_url)

    def run(self):
        gevent.spawn(self.connect_and_run)
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
