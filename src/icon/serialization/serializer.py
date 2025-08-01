from __future__ import annotations

import inspect
import logging
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import pydantic
import pydase.units as u
import pydase.utils.serialization.serializer
import pytz
import sqlalchemy.orm
from pydase.data_service.abstract_data_service import AbstractDataService
from pydase.utils.helpers import get_attribute_doc

from icon.config.config import get_config
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder

if TYPE_CHECKING:
    from pydase.utils.serialization.types import (
        SerializedDatetime,
        SerializedDict,
        SerializedException,
    )

    from icon.serialization.types import SerializedIconObject, SerializedPydanticModel

logger = logging.getLogger(__name__)

timezone = pytz.timezone(get_config().date.timezone)


class IconSerializer(pydase.utils.serialization.serializer.Serializer):
    """
    This serializer adds serialization of pydantic models to the
    `pydase.utils.serialization.serializer.Serializer`.
    """

    @classmethod
    def serialize_object(cls, obj: Any, access_path: str = "") -> SerializedIconObject:  # type: ignore[override] # noqa: C901
        result: SerializedIconObject | None = None

        if isinstance(obj, Exception):
            result = cls._serialize_exception(obj)

        elif isinstance(obj, datetime):
            result = cls._serialize_datetime(obj, access_path=access_path)

        elif isinstance(obj, pydantic.BaseModel):
            result = cls._serialize_pydantic_model(obj, access_path=access_path)

        elif isinstance(obj, sqlalchemy.orm.DeclarativeBase):
            result = cls._serialize_orm(obj, access_path=access_path)

        elif isinstance(obj, AbstractDataService):
            result = cls._serialize_data_service(obj, access_path=access_path)

        elif isinstance(obj, list):
            result = cls._serialize_list(obj, access_path=access_path)

        elif isinstance(obj, dict):
            result = cls._serialize_dict(obj, access_path=access_path)

        # Special handling for u.Quantity
        elif isinstance(obj, u.Quantity):
            result = cls._serialize_quantity(obj, access_path=access_path)

        # Handling for Enums
        elif isinstance(obj, Enum):
            result = cls._serialize_enum(obj, access_path=access_path)

        # Methods and coroutines
        elif inspect.isfunction(obj) or inspect.ismethod(obj):
            result = cls._serialize_method(obj, access_path=access_path)

        elif isinstance(obj, int | float | bool | str | None):
            result = cls._serialize_primitive(obj, access_path=access_path)

        if result is not None:
            return result

        raise pydase.utils.serialization.serializer.SerializationError(
            f"Could not serialized object of type {type(obj)}."
        )

    @classmethod
    def _serialize_datetime(cls, obj: datetime, access_path: str) -> SerializedDatetime:
        return {
            "type": "datetime",
            "value": obj.astimezone(timezone).isoformat(),
            "doc": None,
            "full_access_path": access_path,
            "readonly": True,
        }

    @classmethod
    def _serialize_pydantic_model(
        cls, obj: pydantic.BaseModel, access_path: str
    ) -> SerializedPydanticModel:
        doc = get_attribute_doc(obj)
        dumped_model = obj.model_dump_json()
        return {
            "type": "pydantic.BaseModel",
            "name": f"{obj.__module__}.{type(obj).__name__}",
            "value": dumped_model,
            "doc": doc,
            "full_access_path": access_path,
            "readonly": True,
        }

    @classmethod
    def _serialize_orm(
        cls, obj: sqlalchemy.orm.DeclarativeBase, access_path: str
    ) -> SerializedDict:
        dumped_model = SQLAlchemyDictEncoder.encode(obj=obj)
        return cls._serialize_dict(dumped_model, access_path)

    @classmethod
    def _serialize_exception(cls, obj: Exception) -> SerializedException:
        try:
            value = obj.args[0]
        except Exception:
            value = str(obj)

        return {
            "full_access_path": "",
            "doc": None,
            "readonly": True,
            "type": "Exception",
            "value": value,
            "name": obj.__class__.__name__,
        }


def dump(obj: Any) -> SerializedIconObject:
    return IconSerializer.serialize_object(obj)
