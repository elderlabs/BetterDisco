from websocket import WebSocketApp, setdefaulttimeout

from disco.util.emitter import Emitter
from disco.util.logging import LoggingClass


class Websocket(LoggingClass, WebSocketApp):
    """
    A utility class which wraps the functionality of :class:`websocket.WebSocketApp`
    changing its behavior to better conform with standard style across disco.

    The major difference comes with the move from callback functions, to all
    events being piped into a single emitter.
    """
    def __init__(self, *args, **kwargs):
        LoggingClass.__init__(self)
        setdefaulttimeout(5)
        WebSocketApp.__init__(self, *args, **kwargs)

        self.is_closed = False
        self.emitter = Emitter()

        # Hack to get events to emit
        for var in self.__dict__.keys():
            if not var.startswith('on_'):
                continue

            setattr(self, var, var)

    def _callback(self, callback, *args):
        if not callback:
            return

        self.emitter.emit(callback, *args)
