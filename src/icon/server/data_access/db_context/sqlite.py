import pydase.config
import sqlalchemy

from icon.server.data_access.models.sqlite import Base

if pydase.config.OperationMode().environment == "testing":
    SQLITE_FILE = "icon_testing.db"
elif pydase.config.OperationMode().environment == "development":
    SQLITE_FILE = "icon_dev.db"
else:
    SQLITE_FILE = "icon.db"


SQLITE_URL = f"sqlite:///{SQLITE_FILE}"
engine = sqlalchemy.create_engine(SQLITE_URL, echo=False)


def create_db_and_tables() -> None:
    Base.metadata.create_all(engine)
