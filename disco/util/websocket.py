import websocket

from disco.util.emitter import Emitter
from disco.util.logging import LoggingClass


class Websocket(LoggingClass, websocket.WebSocketApp):
    """
    A utility class which wraps the functionality of :class:`websocket.WebSocketApp`
    changing its behavior to better conform with standard style across disco.

    The major difference comes with the move from callback functions, to all
    events being piped into a single emitter.
    """
    def __init__(self, *args, **kwargs):
        LoggingClass.__init__(self)
        websocket.setdefaulttimeout(5)
        websocket.WebSocketApp.__init__(self, *args, **kwargs)

        self.emitter = Emitter()

        # Hack to get events to emit
        for var in self.__dict__.keys():
            if not var.startswith('on_'):
                continue

            setattr(self, var, var)

    def _get_close_args(self, data):
        if data and len(data) >= 2:
            code = 256 * data[0:1][0] + data[1:2][0]
            reason = str(data[2:], 'utf=8')
            return [code, reason]
        return [None, None]

    def _callback(self, callback, *args):
        if not callback:
            return

        self.emitter.emit(callback, *args)
