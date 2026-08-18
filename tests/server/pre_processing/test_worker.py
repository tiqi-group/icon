from __future__ import annotations

import queue
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import pytest

from icon.server.data_access.models.enums import JobRunStatus, ScanMode
from icon.server.hardware_processing.worker import should_divert_task
from icon.server.pre_processing.worker import (
    PreProcessingWorker,
    get_scan_combinations,
)

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.job import Job
    from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter
    from icon.server.hardware_processing.task import HardwareProcessingTask

# Fixed reference point: the parameter-update timestamp the consumer compares against.
PARAM_UPDATE_TS = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
# The SQLite column is stored without tzinfo (as UTC); mirror that for divert checks.
NAIVE_TS = PARAM_UPDATE_TS.replace(tzinfo=None)
NUM_TASKS = 2  # tasks placed in the queue per test
UPDATED_FREQ = 2.0  # parameter value after a calibration during a pause
MAX_ROUNDS = 5  # bound on consumer<->hardware round-trips before we call it a loop


def _scan_parameters(*, realtime: bool) -> list[Any]:
    """Scan-parameter list that reads as realtime (or not) to contains_realtime_parameter."""
    return [SimpleNamespace(realtime=True)] if realtime else []


class _FakeTask:
    """Minimal stand-in for HardwareProcessingTask (only the attributes touched)."""

    def __init__(
        self,
        created: datetime,
        hardware_instructions: bytes = b"ORIGINAL",
        *,
        realtime: bool = False,
    ) -> None:
        self.created = created
        self.priority = 0
        self.scanned_params: dict[str, Any] = {}
        self.hardware_instructions = hardware_instructions
        # Mirror PreProcessingTask, which exposes scan_parameters both as its own field
        # and via .job (the scheduler sets the field to job.scan_parameters).
        scan_parameters = _scan_parameters(realtime=realtime)
        self.pre_processing_task = SimpleNamespace(
            scan_parameters=scan_parameters,
            job=SimpleNamespace(
                id=1,
                number_of_shots=100,
                scan_parameters=scan_parameters,
            ),
        )

    def __lt__(self, other: _FakeTask) -> bool:
        return (self.priority, self.created) < (other.priority, other.created)


def _fake_task(
    created: datetime,
    hardware_instructions: bytes = b"ORIGINAL",
    *,
    realtime: bool = False,
) -> HardwareProcessingTask:
    """A _FakeTask typed as the real task, so the strongly-typed queues accept it."""
    return cast(
        "HardwareProcessingTask",
        _FakeTask(created, hardware_instructions, realtime=realtime),
    )


def _make_worker() -> tuple[PreProcessingWorker, list[HardwareProcessingTask]]:
    worker = PreProcessingWorker.__new__(PreProcessingWorker)
    worker._parameter_dict = {}
    worker._outdated_tasks = queue.PriorityQueue()
    worker._processed_data_points = queue.Queue()
    submitted: list[HardwareProcessingTask] = []

    def _submit(*, task: HardwareProcessingTask) -> None:
        submitted.append(task)

    worker._submit_task_to_hw_worker = _submit  # type: ignore[method-assign]
    return worker, submitted


def _run_mock(status: JobRunStatus) -> MagicMock:
    # SQLite returns this column without timezone info (stored as UTC), so mirror that.
    return MagicMock(
        status=status,
        parameter_update_timestamp=PARAM_UPDATE_TS.replace(tzinfo=None),
    )


def _run_regenerate(worker: PreProcessingWorker, status: JobRunStatus) -> MagicMock:
    """Run the consumer against a run with the given status; return the generate mock."""
    with (
        patch(
            "icon.server.pre_processing.worker.create_hardware_instructions",
            return_value=b"REGENERATED",
        ) as generate,
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
    ):
        repo.get_run_by_job_id.return_value = _run_mock(status)
        worker._regenerate_outdated_jobs(
            client=cast("Any", object()),
            namespace=cast("Any", object()),
        )
    return generate


def test_regenerate_only_regenerates_stale_tasks() -> None:
    """Pause-diverted (fresh) tasks must not be needlessly regenerated."""
    worker, submitted = _make_worker()
    stale = _fake_task(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    fresh = _fake_task(created=PARAM_UPDATE_TS + timedelta(seconds=10))
    worker._outdated_tasks.put(stale)
    worker._outdated_tasks.put(fresh)

    generate = _run_regenerate(worker, JobRunStatus.PROCESSING)

    assert generate.call_count == 1
    assert len(submitted) == NUM_TASKS
    assert stale.hardware_instructions == b"REGENERATED"
    assert fresh.hardware_instructions == b"ORIGINAL"


def test_regenerate_stops_when_paused() -> None:
    """Draining must stop without feeding a paused hardware worker."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_fake_task(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_fake_task(created=PARAM_UPDATE_TS))

    generate = _run_regenerate(worker, JobRunStatus.PAUSED)

    assert submitted == []
    assert generate.call_count == 0
    assert worker._outdated_tasks.qsize() == NUM_TASKS


def test_regenerate_does_not_regenerate_realtime_tasks() -> None:
    """Realtime tasks keep their last-generated hardware instructions, never the generic regen."""
    worker, submitted = _make_worker()
    stale = _fake_task(created=PARAM_UPDATE_TS - timedelta(seconds=10), realtime=True)
    worker._outdated_tasks.put(stale)

    generate = _run_regenerate(worker, JobRunStatus.PROCESSING)

    assert generate.call_count == 0
    assert submitted == [stale]
    assert stale.hardware_instructions == b"ORIGINAL"


def test_regenerate_drops_cancelled_tasks() -> None:
    """Cancelled jobs' tasks are accounted for directly, not bounced through HW."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_fake_task(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_fake_task(created=PARAM_UPDATE_TS))

    generate = _run_regenerate(worker, JobRunStatus.CANCELLED)

    assert submitted == []
    assert generate.call_count == 0
    assert worker._processed_data_points.qsize() == NUM_TASKS
    assert worker._outdated_tasks.qsize() == 0


def test_regenerate_uses_updated_parameters_after_pause() -> None:
    """A parameter changed during a pause is applied when a stale task is regenerated."""
    worker, submitted = _make_worker()
    worker._parameter_dict = {"freq": UPDATED_FREQ}
    stale = _fake_task(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    worker._outdated_tasks.put(stale)

    generate = _run_regenerate(worker, JobRunStatus.PROCESSING)

    assert submitted == [stale]
    assert stale.hardware_instructions == b"REGENERATED"
    assert generate.call_args.kwargs["parameter_dict"]["freq"] == UPDATED_FREQ


def test_no_tight_loop_on_realtime_resume() -> None:
    """The consumer<->hardware-worker round-trip must terminate for a realtime scan.

    Reproduces the resume-after-parameter-update tight loop: a realtime task made
    stale by a parameter update during a pause bounces between the consumer (which
    resubmits it) and the hardware worker (which re-diverts it as outdated). Any fix
    -- refreshing the task, dropping it, or exempting realtime from the staleness
    divert -- must make the round-trip terminate.
    """
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(
        _fake_task(created=PARAM_UPDATE_TS - timedelta(seconds=10), realtime=True)
    )

    for _ in range(MAX_ROUNDS):
        submitted.clear()
        _run_regenerate(worker, JobRunStatus.PROCESSING)
        # Model the hardware worker: divert each resubmission it still finds outdated.
        for task in submitted:
            if should_divert_task(task, PARAM_UPDATE_TS, JobRunStatus.PROCESSING):
                worker._outdated_tasks.put(task)
        if worker._outdated_tasks.empty():
            break

    assert worker._outdated_tasks.empty()


def test_should_divert_task_diverts_paused() -> None:
    """A paused job always diverts, regardless of scan type or staleness."""
    fresh = _fake_task(created=PARAM_UPDATE_TS + timedelta(seconds=10))
    assert should_divert_task(fresh, NAIVE_TS, JobRunStatus.PAUSED)


def test_should_divert_task_never_diverts_realtime_for_staleness() -> None:
    """Realtime tasks are exempt from the staleness divert (only pause diverts them)."""
    stale_realtime = _fake_task(
        created=PARAM_UPDATE_TS - timedelta(seconds=10), realtime=True
    )
    assert not should_divert_task(stale_realtime, NAIVE_TS, JobRunStatus.PROCESSING)


def test_should_divert_task_staleness_for_regular_scans() -> None:
    """Regular tasks divert only when built before the (tz-naive) parameter update."""
    stale = _fake_task(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    fresh = _fake_task(created=PARAM_UPDATE_TS + timedelta(seconds=10))
    assert should_divert_task(stale, NAIVE_TS, JobRunStatus.PROCESSING)
    assert not should_divert_task(fresh, NAIVE_TS, JobRunStatus.PROCESSING)
    # No parameter update recorded yet -> nothing is stale.
    assert not should_divert_task(stale, None, JobRunStatus.PROCESSING)


def _scan_parameter(
    name: str, scan_values: list[Any], *, realtime: bool = False
) -> ScanParameter:
    """A scan parameter typed as the SQLAlchemy model, without touching the database."""
    param = SimpleNamespace(
        name=name,
        variable_id=name,
        scan_values=scan_values,
        realtime=realtime,
        unique_id=lambda: name,
    )
    return cast("ScanParameter", param)


def _job(
    scan_parameters: list[ScanParameter],
    *,
    scan_mode: ScanMode = ScanMode.MESH,
    repetitions: int = 1,
) -> Job:
    """A job typed as the SQLAlchemy model, without touching the database."""
    return cast(
        "Job",
        SimpleNamespace(
            scan_parameters=scan_parameters,
            scan_mode=scan_mode,
            repetitions=repetitions,
        ),
    )


def test_mesh_scan_combines_every_parameter_value() -> None:
    """A mesh scan yields the cartesian product: n * m data points."""
    job = _job(
        [_scan_parameter("a", [1, 2, 3]), _scan_parameter("b", [10, 20])],
        scan_mode=ScanMode.MESH,
    )

    assert get_scan_combinations(job) == [
        {"a": 1, "b": 10},
        {"a": 1, "b": 20},
        {"a": 2, "b": 10},
        {"a": 2, "b": 20},
        {"a": 3, "b": 10},
        {"a": 3, "b": 20},
    ]


def test_correlated_scan_steps_through_parameters_together() -> None:
    """A correlated scan yields one data point per index: n data points, not n * m."""
    job = _job(
        [
            _scan_parameter("a", [1, 2, 3]),
            _scan_parameter("b", [10, 20, 30]),
            _scan_parameter("c", [100, 200, 300]),
        ],
        scan_mode=ScanMode.CORRELATED,
    )

    assert get_scan_combinations(job) == [
        {"a": 1, "b": 10, "c": 100},
        {"a": 2, "b": 20, "c": 200},
        {"a": 3, "b": 30, "c": 300},
    ]


def test_correlated_scan_repeats_each_data_point() -> None:
    """Repetitions repeat the whole correlated sequence, as they do for mesh scans."""
    job = _job(
        [_scan_parameter("a", [1, 2]), _scan_parameter("b", [10, 20])],
        scan_mode=ScanMode.CORRELATED,
        repetitions=2,
    )

    assert (
        get_scan_combinations(job)
        == [
            {"a": 1, "b": 10},
            {"a": 2, "b": 20},
        ]
        * 2
    )


def test_correlated_scan_ignores_realtime_parameter() -> None:
    """Realtime parameters are scanned as an outer loop, not correlated with the rest."""
    job = _job(
        [
            _scan_parameter("a", [1, 2]),
            _scan_parameter("b", [10, 20]),
            _scan_parameter("Real Time", [1, 1, 1], realtime=True),
        ],
        scan_mode=ScanMode.CORRELATED,
    )

    assert get_scan_combinations(job) == [{"a": 1, "b": 10}, {"a": 2, "b": 20}]


def test_correlated_scan_rejects_unequal_number_of_scan_values() -> None:
    """A correlated scan requires the same number of values for every parameter."""
    job = _job(
        [_scan_parameter("a", [1, 2, 3]), _scan_parameter("b", [10, 20])],
        scan_mode=ScanMode.CORRELATED,
    )

    with pytest.raises(ValueError, match="same number of scan values"):
        get_scan_combinations(job)


def test_mesh_scan_allows_unequal_number_of_scan_values() -> None:
    """The equal-length requirement applies to correlated scans only."""
    job = _job(
        [_scan_parameter("a", [1, 2, 3]), _scan_parameter("b", [10, 20])],
        scan_mode=ScanMode.MESH,
    )

    assert len(get_scan_combinations(job)) == 6  # noqa: PLR2004
