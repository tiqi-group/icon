import logging
import logging.config

import pydase.config

logger = logging.getLogger(__name__)

if pydase.config.OperationMode().environment == "development":
    LOG_LEVEL = logging.DEBUG
else:
    LOG_LEVEL = logging.INFO

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "pydase.utils.logging.DefaultFormatter",
            "fmt": "%(asctime)s.%(msecs)03d | %(levelprefix)s | "
            "%(name)s:%(funcName)s:%(lineno)d - %(message)s",
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
        "icon": {"handlers": ["default"], "level": LOG_LEVEL, "propagate": False},
        "sqlalchemy.engine": {
            "handlers": ["default"],
            "level": logging.INFO if LOG_LEVEL == logging.DEBUG else logging.WARNING,
            "propagate": False,
        },
    },
}


def setup_logging() -> None:
    """
    Configures the logging settings for the application.

    This function sets up logging with specific formatting and colorization of log
    messages. The log level is determined based on the application's operation mode. By
    default, in a development environment, the log level is set to DEBUG, whereas in
    other environments, it is set to INFO.
    """

    logging.config.dictConfig(LOGGING_CONFIG)

    logger.debug("Configured icon logging.")
