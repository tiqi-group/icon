from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import InfluxDBv1Session
from icon.server.data_access.db_context.influxdb_v1 import (
    is_responsive as v1_is_responsive,
)
from icon.server.data_access.db_context.influxdb_v2 import InfluxDBv2Session
from icon.server.data_access.db_context.influxdb_v2 import (
    is_responsive as v2_is_responsive,
)


def get_influxdb_session() -> InfluxDBv1Session | InfluxDBv2Session:
    """Return a session for the configured InfluxDB backend."""
    if get_config().databases.backend == "influxdbv2":
        return InfluxDBv2Session()
    return InfluxDBv1Session()


def get_influxdb_measurement() -> str:
    """Return the measurement name for the configured InfluxDB backend."""
    if get_config().databases.backend == "influxdbv2":
        return get_config().databases.influxdbv2.measurement
    return get_config().databases.influxdbv1.measurement


def is_responsive() -> bool:
    """Check whether the configured InfluxDB backend is reachable."""
    if get_config().databases.backend == "influxdbv2":
        return v2_is_responsive()
    return v1_is_responsive()
