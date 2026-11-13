"""Reproduction for #216: stale local parameters when the client clock lags the server.

Flow under test (only InfluxDB and the client transport are faked):

1. The server writes a new value for a local parameter. InfluxDB stamps the point with
   the *server* clock.
2. The Python client schedules the job right away. ``ExperimentProxy.schedule`` stamps
   ``local_parameters_timestamp`` with the *client* clock.
3. Pre-processing snapshots the experiment's local parameters with
   ``time <= local_parameters_timestamp`` (``LOCALS_FROM_TS_GLOBALS_LATEST``).

If the client clock is behind the server, the write from step 1 has a later timestamp
than the job, so the job silently runs with the previous value.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import pytest

from icon.client.api.experiments_controller import ExperimentProxy
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
from icon.server.pre_processing.worker import ParamUpdateMode, PreProcessingWorker

if TYPE_CHECKING:
    from icon.server.data_access.experiment_data import DatabaseValueType

NAMESPACE = "experiment_library.experiments.exp.Exp.Instance"
PARAM_ID = f"namespace='{NAMESPACE}' parameter_group='g' param_type='float' key='freq'"
OLD_VALUE = 1.0
NEW_VALUE = 2.0

SERVER_NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=UTC)
"""Server (and therefore InfluxDB) wall clock when the new value is written."""
CLIENT_LAG = timedelta(milliseconds=500)
"""How far the client's clock is behind the server's."""


@dataclass
class _Point:
    time: datetime
    namespace: str
    parameter_id: str
    value: DatabaseValueType


class _FakeInfluxBackend:
    """In-memory stand-in for the InfluxDB parameter backend.

    Mirrors the two properties that matter here:
    - writes are timestamped by the *database's* clock (``self.clock``), not the
      caller's, like ``session.write_points`` without an explicit ``time``;
    - reads filter on ``time <= before`` per namespace and return the latest value,
      like ``_where_clause`` + ``ORDER BY time DESC LIMIT 1``.
    """

    def __init__(self) -> None:
        self.clock = SERVER_NOW
        self.points: list[_Point] = []

    def write(
        self, namespace: str, parameter_id: str, value: DatabaseValueType
    ) -> None:
        self.points.append(_Point(self.clock, namespace, parameter_id, value))

    def update_influxdb_parameters(
        self, parameter_mapping: dict[str, DatabaseValueType]
    ) -> None:
        for parameter_id, value in parameter_mapping.items():
            self.write(NAMESPACE, parameter_id, value)

    def get_influxdb_parameters(
        self,
        *,
        before: str | None = None,
        namespace: str | None = None,
        measurement: str | None = None,  # noqa: ARG002
    ) -> dict[str, DatabaseValueType]:
        cutoff = datetime.fromisoformat(before) if before is not None else None
        latest: dict[str, _Point] = {}
        for point in self.points:
            if namespace is not None and point.namespace != namespace:
                continue
            if cutoff is not None and point.time > cutoff:
                continue
            current = latest.get(point.parameter_id)
            if current is None or point.time >= current.time:
                latest[point.parameter_id] = point
        return {pid: point.value for pid, point in latest.items()}


@pytest.fixture
def influx(monkeypatch: pytest.MonkeyPatch) -> _FakeInfluxBackend:
    backend = _FakeInfluxBackend()
    # The old value was written well before anything in the test happens.
    backend.points.append(
        _Point(SERVER_NOW - timedelta(hours=1), NAMESPACE, PARAM_ID, OLD_VALUE)
    )
    monkeypatch.setattr(ParametersRepository, "_backend", backend)
    monkeypatch.setattr(ParametersRepository, "_shared_parameters", {}, raising=False)
    monkeypatch.setattr(ParametersRepository, "initialised", True)
    return backend


def _schedule_from_client(client_now: datetime) -> str:
    """Schedule through the real client API; return the timestamp the server gets."""
    client = MagicMock()
    client.trigger_method.return_value = 1
    proxy = ExperimentProxy(
        client=client, experiment_id="exp", experiment_metadata=MagicMock()
    )
    with patch("icon.client.api.experiments_controller.now", return_value=client_now):
        proxy.schedule()
    timestamp: datetime = client.trigger_method.call_args.kwargs["kwargs"][
        "local_parameters_timestamp"
    ]
    # Same conversion the scheduler does when building the PreProcessingTask.
    return timestamp.isoformat()


def _snapshot_local_parameters(local_parameters_timestamp: str) -> dict[str, Any]:
    """Run the real pre-processing snapshot and return the job's parameter dict."""
    worker = PreProcessingWorker(
        worker_number=0,
        pre_processing_queue=queue.PriorityQueue(),
        update_queue=MagicMock(),
        hardware_processing_queue=queue.PriorityQueue(),
        manager=MagicMock(parameters_dict={}),
        experiment_library_client=MagicMock(),
    )
    task = SimpleNamespace(
        local_parameters_timestamp=local_parameters_timestamp,
        job=SimpleNamespace(id=1),
        job_run=SimpleNamespace(id=1),
    )
    with (
        patch("icon.server.pre_processing.worker.JobRunRepository"),
        patch("icon.server.pre_processing.worker.ExperimentDataRepository"),
    ):
        worker._update_parameter_dict(
            cast("Any", task),
            cast("Any", NAMESPACE),
            mode=ParamUpdateMode.LOCALS_FROM_TS_GLOBALS_LATEST,
        )
    return worker._parameter_dict


def test_job_sees_parameter_set_just_before_scheduling_with_synced_clocks(
    influx: _FakeInfluxBackend,
) -> None:
    """Control: with synchronised clocks the freshly written value is picked up."""
    ParametersRepository.update_parameters(parameter_mapping={PARAM_ID: NEW_VALUE})

    timestamp = _schedule_from_client(client_now=influx.clock)

    assert _snapshot_local_parameters(timestamp)[PARAM_ID] == NEW_VALUE


@pytest.mark.xfail(
    strict=True,
    reason="#216: local_parameters_timestamp comes from the client clock",
)
def test_job_sees_parameter_set_just_before_scheduling_with_lagging_client_clock(
    influx: _FakeInfluxBackend,
) -> None:
    """Bug #216: a client clock 500 ms behind the server makes the job use OLD_VALUE."""
    ParametersRepository.update_parameters(parameter_mapping={PARAM_ID: NEW_VALUE})
    # ICON itself already knows the new value (what the GUI shows) ...
    assert ParametersRepository.get_shared_parameter_by_id(parameter_id=PARAM_ID) == (
        NEW_VALUE
    )

    # ... but the client, whose clock lags, schedules the job "before" the write.
    timestamp = _schedule_from_client(client_now=influx.clock - CLIENT_LAG)

    assert _snapshot_local_parameters(timestamp)[PARAM_ID] == NEW_VALUE
