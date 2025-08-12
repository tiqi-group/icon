import pathlib

import sqlalchemy

from icon.config.config import get_config

sqlite_file = get_config().databases.sqlite.file
if sqlite_file is None:
    raise RuntimeError(
        "The databases.sqlite.file option in your configuration is set to None. You "
        "have to specify a file path for the sqlite database, e.g. "
        "/var/lib/icon/sqlite.db"
    )

sqlite_file_path = pathlib.Path(sqlite_file)
if not sqlite_file_path.parent.exists():
    sqlite_file_path.parent.mkdir()


SQLITE_URL = f"sqlite:///{get_config().databases.sqlite.file}"

engine = sqlalchemy.create_engine(SQLITE_URL, echo=False)
