import logging

import pycrystal.database.local_cache
import pycrystal.experiment
import pycrystal.parameters
from pycrystal.utils.helpers import get_config_from_module_name

log_level = logging.ERROR
logging.basicConfig(level=log_level)
logging.getLogger("pycrystal").setLevel(log_level)
logging.getLogger("ionpulse_sequence_generator").setLevel(log_level)
KEY_VAL_DICT = {key_val_dict}
N_SHOTS = {n_shots}

pycrystal.parameters.Parameter.db = pycrystal.database.local_cache.LocalCache(
    key_val_dict=KEY_VAL_DICT,
)

module_name = "{module_name}"
exp_instance_name = "{exp_instance_name}"

config = get_config_from_module_name(module_name)
exp_config = next(
    instance
    for instance in config["experiment_instances"]
    if instance[1]["name"] == exp_instance_name
)
exp_class = exp_config[0]
exp_kwargs = exp_config[1]
exp_instance = exp_class(**exp_kwargs)


import experiment_library.hardware_description.hardware

experiment_library.hardware_description.hardware.hardware.init()
exp_instance._init()
pycrystal.experiment.Experiment.shots = N_SHOTS
exp_instance._initialize_scan(n_shots=N_SHOTS, debug_level=log_level)
sequence = exp_instance.pulse_sequence()
sequence_json = sequence.get_json_string(exp_instance._sequence_header)
print(sequence_json)
