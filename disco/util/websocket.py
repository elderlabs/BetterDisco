from websocket import WebSocketApp, setdefaulttimeout
from platform import system as platform_system
try:
    from regex import search as re_search
except ImportError:
    from re import search as re_search

from disco.util.emitter import Emitter
from disco.util.logging import LoggingClass


def get_http_status(error):
    """
    Return the HTTP status from a WebSocket handshake failure, if present.
    """
    status = getattr(error, 'status_code', None)
    if status is not None:
        return status

    match = re_search(r'Handshake status (\d{3})\b', str(error))
    return int(match.group(1)) if match else None


class Websocket(LoggingClass, WebSocketApp):
    """
    A utility class which wraps the functionality of :class:`websocket.WebSocketApp`
    changing its behavior to better conform with standard style across disco.

    The major difference comes with the move from callback functions, to all
    events being piped into a single emitter.
    """
    def __init__(self, *args, **kwargs):
        LoggingClass.__init__(self)
        # All other tested operating systems suffer with a timeout of 5 seconds
        if platform_system() == 'Linux':
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
