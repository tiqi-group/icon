import datetime
import enum
from typing import Any

import pydase.units as u
import pytz
import sqlalchemy.orm
from sqlalchemy.orm.attributes import instance_dict

from icon.config.config import get_config

timezone = pytz.timezone(get_config().date.timezone)


class SQLAlchemyDictEncoder:
    @classmethod
    def encode(cls, obj: Any) -> Any:
        """Encodes SQLAlchemy ORM objects and other types into a dictionary format."""
        match obj:
            case sqlalchemy.orm.DeclarativeBase():
                # Get the instance dictionary without triggering lazy loads
                data = instance_dict(obj)
                data.pop("_sa_instance_state", None)  # Remove SQLAlchemy internal state

                return {key: cls.encode(value) for key, value in data.items()}
            case u.Quantity():
                # The frontend consumes scan values as plain numbers (units stay with
                # the parameter metadata); a raw Quantity would break JSON emission.
                return obj.magnitude
            case enum.Enum():
                return obj.value
            case datetime.datetime():
                return obj.astimezone(timezone).isoformat()
            case list():
                return [cls.encode(item) for item in obj]
            case dict():
                return {key: cls.encode(value) for key, value in obj.items()}
            case _:
                return obj
