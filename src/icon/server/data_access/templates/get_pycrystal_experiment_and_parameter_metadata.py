import json
import pkgutil

import experiment_library.experiments
from pycrystal.parameters import Parameter
from pycrystal.utils.helpers import (
    ExperimentDict,
    get_experiment_metadata,
)

experiments: ExperimentDict = {}
for mod_info in pkgutil.iter_modules(experiment_library.experiments.__path__):
    experiment_module = experiment_library.experiments.__name__ + "." + mod_info.name
    experiments.update(get_experiment_metadata(experiment_module=experiment_module))

parameters = {
    "all parameters": Parameter.registry.all_parameters,
    "display groups": {
        f"{namespace} ({display_group})": parameter_dict
        for namespace, display_groups in Parameter.registry.namespace_registry.items()
        for display_group, parameter_dict in display_groups.items()
    },
}


print(
    json.dumps(
        {
            "experiment_metadata": experiments,
            "parameter_metadata": parameters,
        },
        indent=2,
    )
)
