import logging
from typing import TYPE_CHECKING, Any, cast

import pydantic
import pydase
import pydase.components
import pydase.utils.serialization.deserializer
from pydase.utils.serialization.types import SerializedObject

from icon.serialization.types import (
    SerializedIconObject,
    SerializedPydanticModel,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class IconDeserializer(pydase.utils.serialization.deserializer.Deserializer):
    """
    This deserializer adds deserialization of pydantic models to the
    `pydase.utils.serialization.deserializer.Deserializer`.
    """

    @classmethod
    def deserialize(cls, serialized_object: SerializedIconObject) -> Any:
        type_handler: dict[str | None, None | Callable[..., Any]] = {
            None: None,
            "int": cls.deserialize_primitive,
            "float": cls.deserialize_primitive,
            "bool": cls.deserialize_primitive,
            "str": cls.deserialize_primitive,
            "NoneType": cls.deserialize_primitive,
            "Quantity": cls.deserialize_quantity,
            "Enum": cls.deserialize_enum,
            "ColouredEnum": lambda serialized_object: cls.deserialize_enum(
                serialized_object, enum_class=pydase.components.ColouredEnum
            ),
            "list": cls.deserialize_list,
            "dict": cls.deserialize_dict,
            "method": cls.deserialize_method,
            "Exception": cls.deserialize_exception,
            "datetime": cls.deserialize_datetime,
            "pydantic.BaseModel": cls.deserialize_pydantic_basemodel,
        }

        # First go through handled types (as ColouredEnum is also within the components)
        handler = type_handler.get(serialized_object["type"])
        if handler:
            return handler(serialized_object)

        # Custom types like Components or DataService classes
        service_base_class = cls.get_service_base_class(serialized_object["type"])
        if service_base_class:
            return cls.deserialize_data_service(
                cast(SerializedObject, serialized_object), service_base_class
            )

        return None

    @classmethod
    def deserialize_pydantic_basemodel(
        cls, serialized_object: SerializedPydanticModel
    ) -> pydantic.BaseModel:
        def get_model_from_module(module: str, model_name: str) -> pydantic.BaseModel:
            import importlib

            return getattr(importlib.import_module(module), model_name)

        class_module, class_name = serialized_object["name"].rsplit(".", 1)
        return get_model_from_module(class_module, class_name).model_validate_json(
            serialized_object["value"]
        )


def loads(serialized_object: SerializedIconObject) -> Any:
    return IconDeserializer.deserialize(serialized_object)
