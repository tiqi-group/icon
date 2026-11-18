import pathlib
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    from icon.config.config import Config

SQLITE_URL: str | None = None
_engine: Engine | None = None


def initialize_engine(config: "Config") -> None:
    """Create the process-wide engine from the configured SQLite file.

    Must be called once per process before any repository or migration is used.
    """
    global SQLITE_URL, _engine  # noqa: PLW0603
    sqlite_file = config.get().databases.sqlite.file
    sqlite_file_path = pathlib.Path(sqlite_file)
    if not sqlite_file_path.parent.exists():
        sqlite_file_path.parent.mkdir()

    SQLITE_URL = f"sqlite:///{sqlite_file}"
    _engine = sqlalchemy.create_engine(SQLITE_URL, echo=False)


def get_engine() -> Engine:
    """Return the initialised process-wide engine."""
    if _engine is None:
        msg = "The SQLite engine is not initialised; call initialize_engine() first."
        raise RuntimeError(msg)
    return _engine
