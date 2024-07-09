from typing import Literal

from pydase.utils.serialization.types import (
    SerializedObject,
    SerializedObjectBase,
)


class SerializedPydanticModel(SerializedObjectBase):
    type: Literal["pydantic.BaseModel"]
    value: str
    name: str


SerializedIconObject = SerializedObject | SerializedPydanticModel
