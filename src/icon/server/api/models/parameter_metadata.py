from typing import Any, TypedDict


class ParameterMetadata(TypedDict):
    display_name: str
    unit: str
    default_value: float | int
    min_value: float | None
    max_value: float | None
    allowed_values: list[Any] | None
