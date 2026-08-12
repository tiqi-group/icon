"""Tests for the r2 parameter layout served from an InfluxDB v2 server.

``InfluxDBv2ParameterBackend`` takes an injectable session provider, so the Flux
construction and record decoding are exercised here against a fake session without
needing a live InfluxDB.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, cast

from influxdb_client.client.flux_table import FluxRecord
from typing_extensions import Self

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb.parameters_backend import (
    FieldKey,
    InfluxDBv2ParameterBackend,
    r2_measurement_name,
)

if TYPE_CHECKING:
    from types import TracebackType

    from icon.server.data_access.db_context.influxdb.influxdb_v1 import (
        DatabaseValueType,
    )

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
FLOAT_VALUE = 1.5

NAMESPACE_TAGS = {
    "namespace": "test",
    "parameter_group": "Group",
    "param_type": "ParameterTypes.FLOAT",
}
NAMESPACE_ID = (
    "namespace='test' parameter_group='Group' param_type='ParameterTypes.FLOAT'"
)


class FakeTable:
    def __init__(self, records: list[FluxRecord]) -> None:
        self.records = records


class FakeV2Session:
    """Stand-in for `InfluxDBv2Session` recording queries and writes."""

    def __init__(
        self, records: list[FluxRecord] | None = None, bucket: str = "fake-bucket"
    ) -> None:
        self.bucket = bucket
        self.org = "fake-org"
        self._records = records or []
        self.queries: list[str] = []
        self.written: list[dict[str, Any]] = []
        self.time_precision: str | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        return None

    def query_flux(self, flux: str) -> list[FakeTable]:
        self.queries.append(flux)
        return [FakeTable(self._records)]

    def write_points(
        self, points: list[dict[str, Any]], time_precision: str | None = None, **_: Any
    ) -> bool:
        self.written.extend(points)
        self.time_precision = time_precision
        return True


def make_record(
    tags: dict[str, str],
    field: FieldKey,
    value: DatabaseValueType,
    time: datetime = T0,
) -> FluxRecord:
    return FluxRecord(
        table=0,
        values={
            "result": "_result",
            "table": 0,
            "_start": T0 - timedelta(days=1),
            "_stop": T0 + timedelta(days=1),
            "_time": time,
            "_measurement": "irrelevant",
            "_field": field.value,
            "_value": value,
            **tags,
        },
    )


def make_backend(session: FakeV2Session) -> InfluxDBv2ParameterBackend:
    return InfluxDBv2ParameterBackend(session_provider=cast("Any", lambda: session))


def test_measurement_is_r2_prefixed_and_read_from_v2_config() -> None:
    backend = make_backend(FakeV2Session())

    assert backend.measurement == r2_measurement_name(
        get_config().databases.influxdbv2.measurement
    )
    assert backend.measurement.startswith("icon|2|")


def test_get_influxdb_parameters_rebuilds_identifiers_from_tags() -> None:
    session = FakeV2Session(
        [
            make_record(NAMESPACE_TAGS, FieldKey.FLOAT, 1.5),
            make_record(
                {**NAMESPACE_TAGS, "param_type": "ParameterTypes.BOOL"},
                FieldKey.BOOL,
                value=True,
            ),
        ]
    )

    parameters = make_backend(session).get_influxdb_parameters()

    assert parameters == {
        NAMESPACE_ID: 1.5,
        "namespace='test' parameter_group='Group' param_type='ParameterTypes.BOOL'": (
            True
        ),
    }


def test_get_influxdb_parameters_skips_null_values() -> None:
    session = FakeV2Session(
        [make_record(NAMESPACE_TAGS, FieldKey.FLOAT, cast("Any", None))]
    )

    assert make_backend(session).get_influxdb_parameters() == {}


def test_get_influxdb_parameters_prefers_most_recent_type_field() -> None:
    """A parameter that changed type has one series per type field it has used."""
    session = FakeV2Session(
        [
            make_record(NAMESPACE_TAGS, FieldKey.INT, 3, time=T0),
            make_record(
                NAMESPACE_TAGS, FieldKey.FLOAT, 4.5, time=T0 + timedelta(hours=1)
            ),
        ]
    )

    assert make_backend(session).get_influxdb_parameters() == {NAMESPACE_ID: 4.5}


def test_get_influxdb_parameters_queries_the_session_bucket() -> None:
    session = FakeV2Session(bucket="some-other-bucket")

    make_backend(session).get_influxdb_parameters()

    assert 'from(bucket: "some-other-bucket")' in session.queries[0]


def test_get_influxdb_parameters_applies_namespace_and_before_filters() -> None:
    session = FakeV2Session()

    make_backend(session).get_influxdb_parameters(
        namespace="test", before="2026-01-01T00:00:00Z"
    )

    flux = session.queries[0]
    assert 'r.namespace == "test"' in flux
    assert 'stop: time(v: "2026-01-01T00:00:00Z")' in flux


def test_get_influxdb_parameters_honours_measurement_override() -> None:
    session = FakeV2Session()

    make_backend(session).get_influxdb_parameters(measurement="icon|2|Other")

    assert 'r._measurement == "icon|2|Other"' in session.queries[0]


def test_get_influxdb_parameter_by_id_filters_on_every_specifier() -> None:
    session = FakeV2Session([make_record(NAMESPACE_TAGS, FieldKey.FLOAT, FLOAT_VALUE)])

    value = make_backend(session).get_influxdb_parameter_by_id(NAMESPACE_ID)

    assert value == FLOAT_VALUE
    flux = session.queries[0]
    for key, tag_value in NAMESPACE_TAGS.items():
        assert f'r["{key}"] == "{tag_value}"' in flux


def test_get_influxdb_parameter_by_id_returns_none_when_absent() -> None:
    session = FakeV2Session()

    assert make_backend(session).get_influxdb_parameter_by_id(NAMESPACE_ID) is None


def test_get_influxdb_parameter_keys_lists_identifiers() -> None:
    session = FakeV2Session([make_record(NAMESPACE_TAGS, FieldKey.FLOAT, 1.5)])

    assert make_backend(session).get_influxdb_parameter_keys() == [NAMESPACE_ID]


def test_update_influxdb_parameters_writes_typed_fields_and_tags() -> None:
    session = FakeV2Session()
    backend = make_backend(session)

    backend.update_influxdb_parameters(
        {
            NAMESPACE_ID: 1.5,
            "namespace='test' param_type='ParameterTypes.INT'": 3,
            "namespace='test' param_type='ParameterTypes.BOOL'": True,
            "namespace='test' param_type='ParameterTypes.STR'": "hello",
        }
    )

    assert [point["fields"] for point in session.written] == [
        {FieldKey.FLOAT.value: 1.5},
        {FieldKey.INT.value: 3},
        {FieldKey.BOOL.value: True},
        {FieldKey.STR.value: "hello"},
    ]
    assert session.written[0]["tags"] == NAMESPACE_TAGS
    assert {point["measurement"] for point in session.written} == {backend.measurement}
    assert session.time_precision == "n"


def test_written_parameters_round_trip_through_a_read() -> None:
    """What the backend writes decodes back to the identifiers it was given."""
    session = FakeV2Session()
    backend = make_backend(session)
    written_values: dict[str, DatabaseValueType] = {
        NAMESPACE_ID: 1.5,
        "namespace='other' parameter_group='G' param_type='ParameterTypes.INT'": 7,
    }

    backend.update_influxdb_parameters(written_values)

    read_session = FakeV2Session(
        [
            make_record(
                cast("dict[str, str]", point["tags"]),
                FieldKey(next(iter(point["fields"]))),
                next(iter(point["fields"].values())),
            )
            for point in session.written
        ]
    )
    assert make_backend(read_session).get_influxdb_parameters() == written_values
