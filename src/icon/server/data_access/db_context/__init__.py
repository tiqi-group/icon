from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import InfluxDBv1Session
from icon.server.data_access.db_context.influxdb_v2 import InfluxDBv2Session


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
    from icon.server.data_access.db_context import influxdb_v1, influxdb_v2

    if get_config().databases.backend == "influxdbv2":
        return influxdb_v2.is_responsive()
    return influxdb_v1.is_responsive()
