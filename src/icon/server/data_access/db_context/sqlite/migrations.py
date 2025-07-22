import logging
from pathlib import Path

from alembic import command
from alembic import context as alembic_context  # to set a custom flag
from alembic.config import Config

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    logger.info("Running alembic migrations")

    base_path = Path(__file__).parent
    alembic_cfg = Config(str(base_path / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(base_path / "alembic"))

    # Custom flag to prevent env.py from overriding logging
    setattr(alembic_context, "_from_application", True)

    command.upgrade(alembic_cfg, "head")
