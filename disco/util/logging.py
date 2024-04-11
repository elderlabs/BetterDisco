from logging import WARNING, INFO, DEBUG, ERROR, CRITICAL, FATAL, captureWarnings as logging_captureWarnings, \
    basicConfig as logging_basicConfig, getLogger as logging_getLogger, Formatter as logging_Formatter
from sys import stdout as sys_stdout
from warnings import simplefilter as warnings_simplefilter


LEVEL_OVERRIDES = {
    'requests': WARNING,
}

LOG_FORMAT = '[%(levelname)s] %(asctime)s - %(name)s:%(lineno)d - %(message)s'


def setup_logging(**kwargs):
    kwargs.setdefault('format', LOG_FORMAT)
    kwargs.setdefault('stream', sys_stdout)

    # Setup warnings module correctly
    warnings_simplefilter('always', DeprecationWarning)
    logging_captureWarnings(True)

    # Pass through our basic configuration
    logging_basicConfig(**kwargs)

    # handler = logging.StreamHandler()
    # handler.setFormatter(LoggingFormatter)
    # logging.getLogger().addHandler(handler)

    # Override some noisy loggers
    for logger, level in LEVEL_OVERRIDES.items():
        logging_getLogger(logger).setLevel(level)


class LoggingFormatter(logging_Formatter):
    def format(self, record):
        lvl = {
            DEBUG: '[\\x1b[38;21m',
            INFO: '[',
            WARNING: '[\\x1b[33;21m',
            ERROR: '[\\x1b[31;21m',
            CRITICAL: '[\\x1b[33;41m',
            FATAL: '[\\x1b[33;41m',
        }.get(record.levelno, 0)
        self._style._fmt = f'{lvl}%(levelname)s\033[0m] %(asctime)s - %(name)s:%(lineno)d - %(message)s'
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
