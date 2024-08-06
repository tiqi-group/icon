import sqlalchemy

from icon.server.data_access.models.sqlite.base import Base

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = sqlalchemy.create_engine(sqlite_url, echo=False)


def create_db_and_tables() -> None:
    Base.metadata.create_all(engine)
