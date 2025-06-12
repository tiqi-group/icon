import logging

import experiment_library.hardware_description.hardware
import pycrystal.database.influxdbv1
import pycrystal.parameters
from pycrystal.utils.helpers import get_config_from_module_name

log_level = logging.ERROR
logging.basicConfig(level=log_level)
logging.getLogger("pycrystal").setLevel(log_level)
logging.getLogger("ionpulse_sequence_generator").setLevel(log_level)

INFLUXDB_HOST = "{influxdb_host}"
INFLUXDB_PORT = "{influxdb_port}"
INFLUXDB_MEASUREMENT = "{influxdb_measurement}"
INFLUXDB_USERNAME = "{influxdb_username}"
INFLUXDB_PASSWORD = "{influxdb_password}"
INFLUXDB_DATABASE = "{influxdb_database}"
INFLUXDB_SSL = "{influxdb_ssl}"
INFLUXDB_VERIFY_SSL = "{influxdb_verify_ssl}"

pycrystal.parameters.Parameter.db = pycrystal.database.influxdbv1.InfluxDBv1(
    host=INFLUXDB_HOST,
    port=INFLUXDB_PORT,
    measurement=INFLUXDB_MEASUREMENT,
    username=INFLUXDB_USERNAME,
    password=INFLUXDB_PASSWORD,
    database=INFLUXDB_DATABASE,
    ssl=INFLUXDB_SSL,
    verify_ssl=INFLUXDB_VERIFY_SSL,
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


experiment_library.hardware_description.hardware.hardware.init()
exp_instance._init()
exp_instance._initialize_scan(debug_level=log_level)
sequence = exp_instance.pulse_sequence()
sequence_json = sequence.get_json_string(exp_instance._sequence_header)
print(sequence_json)
