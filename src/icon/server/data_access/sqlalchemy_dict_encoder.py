import datetime
import enum
from typing import Any

import pytz
import sqlalchemy.orm
from sqlalchemy.orm.attributes import instance_dict


class SQLAlchemyDictEncoder:
    def __init__(self, timezone: pytz.BaseTzInfo) -> None:
        self.timezone = timezone

    def encode(self, obj: Any) -> Any:
        """Encodes SQLAlchemy ORM objects and other types into a dictionary format."""
        if isinstance(obj, sqlalchemy.orm.DeclarativeBase):
            # Get the instance dictionary without triggering lazy loads
            data = instance_dict(obj)
            data.pop("_sa_instance_state", None)  # Remove SQLAlchemy internal state

            return {key: self.encode(value) for key, value in data.items()}

        if isinstance(obj, enum.Enum):
            return obj.value

        if isinstance(obj, datetime.datetime):
            return obj.astimezone(self.timezone).isoformat()

        if isinstance(obj, list):
            return [self.encode(item) for item in obj]

        if isinstance(obj, dict):
            return {key: self.encode(value) for key, value in obj.items()}

        return obj
