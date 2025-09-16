import pathlib

import sqlalchemy

from icon.config.config import get_config

sqlite_file = get_config().databases.sqlite.file

sqlite_file_path = pathlib.Path(sqlite_file)
if not sqlite_file_path.parent.exists():
    sqlite_file_path.parent.mkdir()


SQLITE_URL = f"sqlite:///{sqlite_file}"

engine = sqlalchemy.create_engine(SQLITE_URL, echo=False)
