import logging
import sys
import warnings


LEVEL_OVERRIDES = {
    'requests': logging.WARNING,
}

LOG_FORMAT = '[%(levelname)s] %(asctime)s - %(name)s:%(lineno)d - %(message)s'


def setup_logging(**kwargs):
    kwargs.setdefault('format', LOG_FORMAT)
    kwargs.setdefault('stream', sys.stdout)

    # Setup warnings module correctly
    warnings.simplefilter('always', DeprecationWarning)
    logging.captureWarnings(True)

    # Pass through our basic configuration
    logging.basicConfig(**kwargs)

    # handler = logging.StreamHandler()
    # handler.setFormatter(LoggingFormatter)
    # logging.getLogger().addHandler(handler)

    # Override some noisy loggers
    for logger, level in LEVEL_OVERRIDES.items():
        logging.getLogger(logger).setLevel(level)


class LoggingFormatter(logging.Formatter):
    def format(self, record):
        lvl = {
            logging.DEBUG: '[\\x1b[38;21m',
            logging.INFO: '[',
            logging.WARNING: '[\\x1b[33;21m',
            logging.ERROR: '[\\x1b[31;21m',
            logging.CRITICAL: '[\\x1b[33;41m',
            logging.FATAL: '[\\x1b[33;41m',
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
            self._log = logging.getLogger(self.__class__.__name__)
            return self._log
