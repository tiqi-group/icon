import json
import pkgutil
from typing import Any, TypedDict

import experiment_library.experiments
from pycrystal.parameter_registry import ParameterMetadata
from pycrystal.utils.helpers import (
    get_config_from_module_name,
    get_experiment_instance_display_groups,
)


class ExperimentMetadata(TypedDict):
    class_name: str
    constructor_kwargs: dict[str, Any]
    parameters: dict[str, dict[str, ParameterMetadata]]


ExperimentDict = dict[str, dict[str, ExperimentMetadata]]


experiments: ExperimentDict = {}
for mod_info in pkgutil.iter_modules(experiment_library.experiments.__path__):
    experiment_module = experiment_library.experiments.__name__ + "." + mod_info.name
    config = get_config_from_module_name(experiment_module)
    for experiment, experiment_instance_kwargs in config["experiment_instances"]:
        experiment_instance_name = experiment_instance_kwargs["name"]
        experiment_identifier = f"{experiment_module}.{experiment.__name__} ({experiment_instance_name})"
        experiments[experiment_identifier] = {
            "class_name": experiment.__name__,
            "constructor_kwargs": experiment_instance_kwargs,
            "parameters": get_experiment_instance_display_groups(
                experiment_module, experiment_instance_name
            ),
        }


# parameters["registry"] = Parameter.registry
print(json.dumps(experiments, indent=2))
