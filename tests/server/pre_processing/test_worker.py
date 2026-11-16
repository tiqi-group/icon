from __future__ import annotations

import asyncio
import multiprocessing
import queue
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

from icon.server.data_access.models.enums import JobRunStatus
from icon.server.hardware_processing.worker import should_divert_task
from icon.server.pre_processing.worker import (
    ExperimentIdentifier,
    PreProcessingWorker,
    create_hardware_instructions,
    create_hardware_instructions_batch,
)
from icon.server.shared_resource_manager import ScanProgress

if TYPE_CHECKING:
    from icon.server.hardware_processing.task import HardwareProcessingTask

# Fixed reference point: the parameter-update timestamp the consumer compares against.
PARAM_UPDATE_TS = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
# The SQLite column is stored without tzinfo (as UTC); mirror that for divert checks.
NAIVE_TS = PARAM_UPDATE_TS.replace(tzinfo=None)
NUM_TASKS = 2  # tasks placed in the queue per test
RUN_ID = 1  # the job run the worker is currently scanning
STALE_RUN_ID = 99  # a job run that finished before the current one started
UPDATED_FREQ = 2.0  # parameter value after a calibration during a pause
MAX_ROUNDS = 5  # bound on consumer<->hardware round-trips before we call it a loop
DEVICE_ORDER = ["main", "sub"]  # the job run's device order, loaded when it starts
POOL_SIZE = 4  # data points whose hardware instructions are generated concurrently
NUM_DATA_POINTS = 10  # data points of the regular scan


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
        run_id: int = RUN_ID,
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
            job_run=SimpleNamespace(id=run_id),
            job=SimpleNamespace(
                id=1,
                number_of_shots=100,
                scan_parameters=scan_parameters,
            ),
        )
        self.data_point_index = 0

    def __lt__(self, other: _FakeTask) -> bool:
        return (self.priority, self.created) < (other.priority, other.created)


def _fake_task(
    created: datetime,
    hardware_instructions: bytes = b"ORIGINAL",
    *,
    realtime: bool = False,
    run_id: int = RUN_ID,
) -> HardwareProcessingTask:
    """A _FakeTask typed as the real task, so the strongly-typed queues accept it."""
    return cast(
        "HardwareProcessingTask",
        _FakeTask(created, hardware_instructions, realtime=realtime, run_id=run_id),
    )


def _make_worker() -> tuple[PreProcessingWorker, queue.PriorityQueue[Any]]:
    hw_queue: queue.PriorityQueue[Any] = queue.PriorityQueue()
    worker = PreProcessingWorker(
        worker_number=0,
        pre_processing_queue=queue.PriorityQueue(),
        update_queue=multiprocessing.Queue(),
        hardware_processing_queue=hw_queue,
        manager=MagicMock(
            PriorityQueue=queue.PriorityQueue,
            Queue=queue.Queue,
            ScanProgress=ScanProgress,
        ),
        experiment_library_client=MagicMock(),
    )
    worker._scan_progress.start(RUN_ID)
    return worker, hw_queue


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
    assert submitted.qsize() == NUM_TASKS
    assert stale.hardware_instructions == b"REGENERATED"
    assert fresh.hardware_instructions == b"ORIGINAL"


def test_regenerate_stops_when_paused() -> None:
    """Draining must stop without feeding a paused hardware worker."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_fake_task(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_fake_task(created=PARAM_UPDATE_TS))

    generate = _run_regenerate(worker, JobRunStatus.PAUSED)

    assert submitted.empty()
    assert generate.call_count == 0
    assert worker._outdated_tasks.qsize() == NUM_TASKS


def test_regenerate_does_not_regenerate_realtime_tasks() -> None:
    """Realtime tasks keep their last-generated hardware instructions, never the generic regen."""
    worker, submitted = _make_worker()
    stale = _fake_task(created=PARAM_UPDATE_TS - timedelta(seconds=10), realtime=True)
    worker._outdated_tasks.put(stale)

    generate = _run_regenerate(worker, JobRunStatus.PROCESSING)

    assert generate.call_count == 0
    assert submitted.queue == [stale]
    assert stale.hardware_instructions == b"ORIGINAL"


def test_regenerate_drops_cancelled_tasks() -> None:
    """Cancelled jobs' tasks are accounted for directly, not bounced through HW."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_fake_task(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_fake_task(created=PARAM_UPDATE_TS))

    generate = _run_regenerate(worker, JobRunStatus.CANCELLED)

    assert submitted.empty()
    assert generate.call_count == 0
    assert worker._scan_progress.completed(RUN_ID) == NUM_TASKS
    assert worker._outdated_tasks.qsize() == 0


def test_regenerate_uses_updated_parameters_after_pause() -> None:
    """A parameter changed during a pause is applied when a stale task is regenerated."""
    worker, submitted = _make_worker()
    worker._parameter_dict = {"freq": UPDATED_FREQ}
    worker._device_order = DEVICE_ORDER
    stale = _fake_task(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    worker._outdated_tasks.put(stale)

    generate = _run_regenerate(worker, JobRunStatus.PROCESSING)

    assert submitted.queue == [stale]
    assert stale.hardware_instructions == b"REGENERATED"
    assert generate.call_args.kwargs["parameter_dict"]["freq"] == UPDATED_FREQ
    assert generate.call_args.kwargs["device_order"] == DEVICE_ORDER


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
        while not submitted.empty():
            submitted.get()
        _run_regenerate(worker, JobRunStatus.PROCESSING)
        # Model the hardware worker: divert each resubmission it still finds outdated.
        while not submitted.empty():
            task = submitted.get()
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


def test_create_hardware_instructions_follows_the_job_runs_device_order() -> None:
    """The devices follow the given order, unordered ones last.

    The order is not loaded from the library for every data point.
    """

    class _Client:
        async def load_device_order(self) -> list[str]:
            raise AssertionError("The device order is loaded once per job run")

        async def create_hardware_instructions(self, **_: Any) -> dict[str, str]:
            return {
                device_id: f"{device_id} instructions"
                for device_id in ["sub", "extra", "main"]
            }

    assert create_hardware_instructions(
        cast("Any", _Client()),
        n_shots=1,
        parameter_dict={},
        device_order=DEVICE_ORDER,
        namespace=ExperimentIdentifier("module", "Class", "instance"),
    ) == [
        ("main", "main instructions"),
        ("sub", "sub instructions"),
        ("extra", "extra instructions"),
    ]


def test_create_hardware_instructions_batch_keeps_the_data_point_order() -> None:
    """Results follow the data points, even when later ones finish first."""

    class _Client:
        async def create_hardware_instructions(
            self, *, parameter_dict: dict[str, Any], **_: Any
        ) -> dict[str, str]:
            x = parameter_dict["x"]
            await asyncio.sleep(0.01 * (POOL_SIZE - x))
            return {"sub": f"sub {x}", "main": f"main {x}"}

    assert create_hardware_instructions_batch(
        cast("Any", _Client()),
        n_shots=1,
        parameter_dicts=[{"x": x} for x in range(POOL_SIZE)],
        device_order=DEVICE_ORDER,
        namespace=ExperimentIdentifier("module", "Class", "instance"),
    ) == [[("main", f"main {x}"), ("sub", f"sub {x}")] for x in range(POOL_SIZE)]


def test_regular_scan_submits_batches_in_data_point_order() -> None:
    """Instructions are generated a pool at a time; tasks are submitted in order."""
    worker, _ = _make_worker()
    lane: queue.Queue[Any] = queue.Queue()
    worker._hw_processing_queue = lane
    batch_sizes: list[int] = []

    def generate_batch(
        _client: Any, *, parameter_dicts: list[dict[str, Any]], **_: Any
    ) -> list[list[tuple[str, str]]]:
        batch_sizes.append(len(parameter_dicts))
        return [[("main", str(p["x"]))] for p in parameter_dicts]

    def create_task(**kwargs: Any) -> Any:
        # Model the hardware worker finishing the data point.
        worker._scan_progress.complete(RUN_ID)
        return SimpleNamespace(
            data_point_index=kwargs["index"],
            hardware_instructions=kwargs["hardware_instructions"],
            created=kwargs["created"],
            pre_processing_task=kwargs["pre_processing_task"],
        )

    scan_parameter = SimpleNamespace(
        realtime=False, unique_id=lambda: "x", scan_values=list(range(NUM_DATA_POINTS))
    )
    pre_processing_task = SimpleNamespace(
        job=SimpleNamespace(
            id=1, number_of_shots=100, repetitions=1, scan_parameters=[scan_parameter]
        ),
        job_run=SimpleNamespace(id=RUN_ID),
    )
    with (
        patch("icon.server.pre_processing.worker.get_config") as config,
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
        patch(
            "icon.server.pre_processing.worker.create_hardware_instructions_batch",
            side_effect=generate_batch,
        ),
        patch.object(worker, "_create_hardware_task", side_effect=create_task),
    ):
        config.return_value.server.pre_processing.instruction_pool_size = POOL_SIZE
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.PROCESSING)
        for _ in worker._handle_regular_scan(
            cast("Any", pre_processing_task),
            namespace=cast("Any", object()),
            client=cast("Any", object()),
            src_dir=None,
        ):
            pass

    tasks = list(lane.queue)
    assert batch_sizes == [4, 4, 2]
    assert [task.data_point_index for task in tasks] == list(range(NUM_DATA_POINTS))
    assert [task.hardware_instructions for task in tasks] == [
        [("main", str(x))] for x in range(NUM_DATA_POINTS)
    ]
    assert len({task.created for task in tasks[:POOL_SIZE]}) == 1
