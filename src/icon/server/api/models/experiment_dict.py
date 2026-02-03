from dataclasses import dataclass
from typing import Any

from icon.server.api.models.parameter_metadata import ParameterMetadata


@dataclass
class ExperimentMetadata:
    """Metadata for a single experiment."""

    class_name: str
    """Name of the experiment class."""
    constructor_kwargs: dict[str, Any]
    """Constructor keyword arguments used to instantiate the experiment."""
    parameters: dict[str, dict[str, ParameterMetadata]]
    """Mapping of display groups to parameter metadata."""


ExperimentDict = dict[str, ExperimentMetadata]
"""Dictionary mapping the unique experiment identifier to its metadata.

Example:
    ```python
    experiment_dict: ExperimentDict = {
        "experiment_library.experiments.my_experiment.MyExperiment (Cool Det)": ExperimentMetadata(
            class_name="MyExperiment",
            constructor_kwargs={
                "name": "Cool Det",
            },
            parameters={
                "Local Parameters": {
                    "namespace='experiment_library.experiments.my_experiment.MyExperiment.Cool Det' parameter_group='default' param_type='ParameterTypes.AMPLITUDE'": {
                        "allowed_values": None,
                        "default_value": 0.0,
                        "display_name": "amplitude",
                        "max_value": 100.0,
                        "min_value": 0.0,
                        "unit": "%",
                    },
                },
                "ParameterGroup": {
                    "namespace='experiment_library.globals.global_parameters' parameter_group='ParameterGroup' param_type='ParameterTypes.AMPLITUDE'": {
                        "allowed_values": None,
                        "default_value": 0.0,
                        "display_name": "amplitude",
                        "max_value": 100.0,
                        "min_value": 0.0,
                        "unit": "%",
                    },
                },
            },
        ),
    }
    ```
"""  # noqa: E501
