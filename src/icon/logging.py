import logging
import logging.config

logger = logging.getLogger(__name__)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "pydase.utils.logging.DefaultFormatter",
            "fmt": "%(asctime)s.%(msecs)03d | %(levelprefix)s | "
            "[%(processName)s | %(threadName)s]"
            " %(name)s:%(funcName)s:%(lineno)d - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "stdout": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "pydase.server.server": {
            "handlers": ["stdout"],
            "level": logging.INFO,
            "propagate": False,
        },
        "pydase.server.web_server.web_server": {
            "handlers": ["stdout"],
            "level": logging.INFO,
            "propagate": False,
        },
        "icon": {"handlers": ["default"], "propagate": False},  # level set at runtime
        "pydase": {"handlers": ["default"], "propagate": False},  # level set at runtime
        "asyncio": {"handlers": ["default"], "level": logging.INFO, "propagate": True},
        "socketio": {
            "handlers": ["default"],
            "level": logging.WARNING,
            "propagate": True,
        },
        "sqlalchemy.engine": {
            "handlers": ["default"],
            "level": logging.WARNING,
            "propagate": True,
        },
        "alembic": {"handlers": ["default"], "propagate": True},  # level set at runtime
        "aiohttp": {"handlers": ["default"], "propagate": True},  # level set at runtime
    },
}


def setup_logging(log_level: int) -> None:
    """Configure the logging system for the application.

    This function applies the application's logging configuration and sets the log level
    for the main 'icon' and 'pydase' loggers. The log level should be determined by the
    caller, typically based on command-line arguments such as '-v' (increase verbosity)
    or '-q' (decrease verbosity).

    Args:
        log_level: The logging level (e.g., logging.DEBUG, logging.INFO,
            logging.WARNING).

    Notes:
        - By default, the log level is WARNING.
        - Each '-v' flag decreases the threshold (e.g., WARNING → INFO → DEBUG).
        - Each '-q' flag increases the threshold (e.g., WARNING → ERROR → CRITICAL).
    """

    LOGGING_CONFIG["loggers"]["icon"]["level"] = log_level
    LOGGING_CONFIG["loggers"]["pydase"]["level"] = log_level
    LOGGING_CONFIG["loggers"]["alembic"]["level"] = log_level
    LOGGING_CONFIG["loggers"]["aiohttp"]["level"] = log_level
    logging.config.dictConfig(LOGGING_CONFIG)

    logger.info("Configured log level: %s", logging.getLevelName(log_level))
