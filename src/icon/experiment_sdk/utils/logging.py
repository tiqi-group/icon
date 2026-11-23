import logging
import logging.config

logger = logging.getLogger(__name__)

DEFAULT_LOG_LEVEL = logging.DEBUG

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "ionpulse_sequence_generator.utils.logging.DefaultFormatter",
            "fmt": "%(asctime)s.%(msecs)03d | %(levelprefix)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",  # noqa: E501
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "pycrystal": {
            "handlers": ["default"],
            "level": DEFAULT_LOG_LEVEL,
            "propagate": False,
        },
    },
}


def setup_logging() -> None:
    """Configures the logging settings for the application."""

    logger.debug("Configuring pycrystal logging.")

    logging.config.dictConfig(LOGGING_CONFIG)
    logging.getLogger("ionpulse_sequence_generator").setLevel(DEFAULT_LOG_LEVEL)
