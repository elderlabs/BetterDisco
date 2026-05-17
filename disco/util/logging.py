import sys
from logging import WARNING, INFO, DEBUG, ERROR, CRITICAL, NOTSET, captureWarnings as logging_captureWarnings, \
    getLogger as logging_getLogger, Formatter as logging_Formatter, StreamHandler as logging_StreamHandler
from warnings import simplefilter as warnings_simplefilter

LEVEL_OVERRIDES = {
    'requests': INFO,
    'urllib3.connectionpool': INFO
}

LOG_FORMAT = '[%(levelname)s] %(asctime)s - %(name)s:%(lineno)d - %(message)s'


def _log_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.excepthook(exc_type, exc_value, exc_traceback)
        return

    logging_getLogger('exception').error(
        'Uncaught exception',
        exc_info=(exc_type, exc_value, exc_traceback),
    )


def _patch_gevent_spawn():
    import gevent

    if getattr(gevent, '_disco_logging_spawn_patched', False):
        return

    original_spawn = gevent.spawn

    def spawn(*args, **kwargs):
        greenlet = original_spawn(*args, **kwargs)

        if not getattr(greenlet, '_disco_logging_linked', False):
            greenlet._disco_logging_linked = True
            greenlet.link_exception(_log_greenlet_exception)

        return greenlet

    gevent.spawn = spawn
    gevent._disco_logging_spawn_patched = True


def _log_greenlet_exception(greenlet):
    if greenlet.successful():
        return

    try:
        greenlet.get()
    except Exception:
        logging_getLogger('gevent.spawn').error(
            'Unhandled exception in spawned greenlet', exc_info=True
        )


def _patch_emitter():
    try:
        from disco.util import emitter as disco_emitter
    except Exception:
        return

    if getattr(disco_emitter.Emitter.emit, '_disco_logging_patched', False):
        return

    original_emit = disco_emitter.Emitter.emit

    def emit(self, name, *args, **kwargs):
        try:
            return original_emit(self, name, *args, **kwargs)
        except Exception:
            self.log.error('Unhandled exception while emitting event `%s`', name, exc_info=True)
            raise

    emit._disco_logging_patched = True
    disco_emitter.Emitter.emit = emit


def setup_logging(**kwargs):
    # Setup warnings module correctly
    warnings_simplefilter('always', DeprecationWarning)
    logging_captureWarnings(True)

    root = logging_getLogger()

    if not root.handlers:
        handler = StreamHandler()
        handler.setFormatter(LoggingFormatter())
        root.addHandler(handler)

    for key, value in kwargs.items():
        setattr(root, key, value)

    formatter = LoggingFormatter()
    for handler in root.handlers:
        handler.setFormatter(formatter)

    sys.excepthook = _log_uncaught_exception
    _patch_gevent_spawn()
    _patch_emitter()

    # Override noisy loggers
    for logger, level in LEVEL_OVERRIDES.items():
        logging_getLogger(logger).setLevel(level)


def find_external_caller():
    frame = sys._getframe(0)
    while frame:
        # Check if the frame's module is different from the current module
        module_name = frame.f_globals.get('__name__')
        if module_name and not module_name.startswith('disco.'):
            return f'{module_name}.{frame.f_code.co_name}()'
        frame = frame.f_back
    return None


class StreamHandler(logging_StreamHandler):
    def emit(self, record):
        if record.levelno >= ERROR:
            self.stream = sys.stderr
        else:
            self.stream = sys.stdout

        super().emit(record)


class LoggingFormatter(logging_Formatter):
    def __init__(self):
        super().__init__(LOG_FORMAT)

    def format(self, record):
        lvl = {
            NOTSET: '[',
            DEBUG: '[',
            INFO: '[',
            WARNING: '[\033[33m',
            ERROR: '[\033[31m',
            CRITICAL: '[\033[33;41m',
        }.get(record.levelno, '[')
        self._style._fmt = f'\033[0m{lvl}%(levelname)s\033[0m] %(asctime)s - %(name)s\033[1;30m:%(lineno)d\033[0m - %(message)s\033[0m'
        return super().format(record)


class LoggingClass:
    __slots__ = ['_log']

    @property
    def log(self):
        try:
            return self._log
        except AttributeError:
            self._log = logging_getLogger(self.__class__.__name__)
            return self._log

    def log_exception(self, message=None, level=ERROR, *args, **kwargs):
        if message is None:
            message = 'Unhandled exception'

        kwargs.setdefault('exc_info', True)
        self.log.log(level, message, *args, **kwargs)
        return kwargs['exc_info'] if isinstance(kwargs['exc_info'], tuple) else sys.exc_info()[1]
