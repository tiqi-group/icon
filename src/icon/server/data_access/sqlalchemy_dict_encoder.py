import datetime
import enum
from typing import Any

import pytz
import sqlalchemy.orm
from sqlalchemy.orm.attributes import instance_dict

from icon.config.config import get_config

timezone = pytz.timezone(get_config().date.timezone)


class SQLAlchemyDictEncoder:
    @classmethod
    def encode(cls, obj: Any) -> Any:
        """Encodes SQLAlchemy ORM objects and other types into a dictionary format."""

        if isinstance(obj, sqlalchemy.orm.DeclarativeBase):
            # Get the instance dictionary without triggering lazy loads
            data = instance_dict(obj)
            data.pop("_sa_instance_state", None)  # Remove SQLAlchemy internal state

            return {key: cls.encode(value) for key, value in data.items()}

        if isinstance(obj, enum.Enum):
            return obj.value

        if isinstance(obj, datetime.datetime):
            return obj.astimezone(timezone).isoformat()

        if isinstance(obj, list):
            return [cls.encode(item) for item in obj]

        if isinstance(obj, dict):
            return {key: cls.encode(value) for key, value in obj.items()}

        return obj
