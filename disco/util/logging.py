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

    # Override some noisy loggers
    for logger, level in LEVEL_OVERRIDES.items():
        logging.getLogger(logger).setLevel(level)


class LoggingClass:
    __slots__ = ['_log']

    @property
    def log(self):
        try:
            return self._log
        except AttributeError:
            self._log = logging.getLogger(self.__class__.__name__)
            return self._log
