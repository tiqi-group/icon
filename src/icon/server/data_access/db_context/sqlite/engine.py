import pydase.config
import sqlalchemy

if pydase.config.OperationMode().environment == "testing":
    SQLITE_FILE = "icon_testing.db"
elif pydase.config.OperationMode().environment == "development":
    SQLITE_FILE = "icon_dev.db"
else:
    SQLITE_FILE = "icon.db"


SQLITE_URL = f"sqlite:///{SQLITE_FILE}"
engine = sqlalchemy.create_engine(SQLITE_URL, echo=False)
