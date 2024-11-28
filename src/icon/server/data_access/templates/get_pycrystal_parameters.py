import json
import pkgutil
from typing import Any, TypedDict

import experiment_library.experiments
import experiment_library.globals.global_parameters
from pycrystal.parameter_registry import ParameterMetadata
from pycrystal.parameters import Parameter
from pycrystal.utils.helpers import (
    get_config_from_module_name,
    get_display_group_list_from_module_name,
    get_experiment_instance_display_groups,
)


class ExperimentMetadata(TypedDict):
    class_name: str
    constructor_kwargs: dict[str, Any]
    parameters: dict[str, dict[str, ParameterMetadata]]


ExperimentDict = dict[str, dict[str, ExperimentMetadata]]


for mod_info in pkgutil.iter_modules(experiment_library.experiments.__path__):
    experiment_module = experiment_library.experiments.__name__ + "." + mod_info.name
    config = get_config_from_module_name(experiment_module)
    for experiment, experiment_instance_kwargs in config["experiment_instances"]:
        experiment_instance_name = experiment_instance_kwargs["name"]
        get_experiment_instance_display_groups(
            experiment_module, experiment_instance_name
        )


parameters = {}
parameters["all parameters"] = Parameter.registry.all_parameters
parameters["Globals"] = get_display_group_list_from_module_name(
    experiment_library.globals.global_parameters.__name__
)

print(json.dumps(parameters, indent=2))
