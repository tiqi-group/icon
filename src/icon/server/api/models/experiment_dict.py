from typing import Any, TypedDict

from icon.server.api.models.parameter_metadata import (
    ParameterMetadata,
)


class ExperimentMetadata(TypedDict):
    class_name: str
    constructor_kwargs: dict[str, Any]
    parameters: dict[str, dict[str, ParameterMetadata]]


ExperimentDict = dict[str, dict[str, ExperimentMetadata]]
