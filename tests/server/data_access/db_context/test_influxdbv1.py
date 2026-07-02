import pytest

from icon.server.data_access.db_context.influxdb_v1 import InfluxDBv1Session

# ``InfluxDBv1Session`` is a schema-agnostic InfluxDB client: it only writes points and
# runs raw queries. Parameter-schema behaviour (typed vs. legacy field layouts) is owned
# and tested in ``tests/server/data_access/repositories/test_parameters_repository.py``.


@pytest.mark.container
def test_write_and_query_round_trip(influxdbv1_service: None) -> None:  # noqa: ARG001
    measurement = "PytestGeneric"
    with InfluxDBv1Session() as session:
        session.query(f'DROP MEASUREMENT "{measurement}"')
        session.write_points(
            [
                {
                    "measurement": measurement,
                    "tags": {"host": "a"},
                    "fields": {"value": 1},
                },
                {
                    "measurement": measurement,
                    "tags": {"host": "b"},
                    "fields": {"value": 2},
                },
            ]
        )

        points = list(
            session.query(f'SELECT "value" FROM "{measurement}"').get_points()
        )
        assert sorted(point["value"] for point in points) == [1, 2]

        assert measurement in session.get_measurements()
        assert session.get_field_keys(measurement) == ["value"]
