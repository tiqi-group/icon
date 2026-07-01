import queue
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from icon.server.data_access.models.enums import JobRunStatus
from icon.server.hardware_processing.worker import should_divert_task
from icon.server.pre_processing.worker import PreProcessingWorker

# Fixed reference point: the parameter-update timestamp the consumer compares against.
PARAM_UPDATE_TS = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
NUM_TASKS = 2  # tasks placed in the queue per test
UPDATED_FREQ = 2.0  # parameter value after a calibration during a pause
MAX_ROUNDS = 5  # bound on consumer<->hardware round-trips before we call it a loop


def _scan_parameters(*, realtime: bool) -> list:
    """Scan-parameter list that reads as realtime (or not) to contains_realtime_parameter."""
    return [SimpleNamespace(realtime=True)] if realtime else []


class _FakeTask:
    """Minimal stand-in for HardwareProcessingTask (only the attributes touched)."""

    def __init__(
        self,
        created: datetime,
        sequence_json: str = "ORIGINAL",
        *,
        realtime: bool = False,
    ) -> None:
        self.created = created
        self.priority = 0
        self.scanned_params: dict = {}
        self.sequence_json = sequence_json
        # Mirror PreProcessingTask, which exposes scan_parameters both as its own field
        # and via .job (the scheduler sets the field to job.scan_parameters).
        scan_parameters = _scan_parameters(realtime=realtime)
        self.pre_processing_task = SimpleNamespace(
            scan_parameters=scan_parameters,
            job=SimpleNamespace(
                number_of_shots=100,
                scan_parameters=scan_parameters,
            ),
        )

    def __lt__(self, other: "_FakeTask") -> bool:
        return (self.priority, self.created) < (other.priority, other.created)


def _make_worker() -> tuple[PreProcessingWorker, list[_FakeTask]]:
    worker = PreProcessingWorker.__new__(PreProcessingWorker)
    worker._parameter_dict = {}
    worker._outdated_tasks = queue.PriorityQueue()
    worker._processed_data_points = queue.Queue()
    submitted: list[_FakeTask] = []
    worker._submit_task_to_hw_worker = lambda *, task: submitted.append(task)
    return worker, submitted


def _run_mock(status: JobRunStatus) -> MagicMock:
    # SQLite returns this column without timezone info (stored as UTC), so mirror that.
    return MagicMock(
        status=status,
        parameter_update_timestamp=PARAM_UPDATE_TS.replace(tzinfo=None),
    )


def _run_regenerate(
    worker: PreProcessingWorker,
    status: JobRunStatus,
    *,
    realtime: bool = False,
) -> MagicMock:
    """Run the consumer against a run with the given status; return the generate mock."""
    with (
        patch(
            "icon.server.pre_processing.worker.generate_sequence_json",
            return_value="REGENERATED",
        ) as generate,
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
    ):
        repo.get_run_by_job_id.return_value = _run_mock(status)
        worker._regenerate_outdated_jobs(
            client=object(),
            pre_processing_task=SimpleNamespace(
                job=SimpleNamespace(
                    id=1, scan_parameters=_scan_parameters(realtime=realtime)
                ),
                job_run=SimpleNamespace(id=1),
            ),
            namespace=object(),
        )
    return generate


def test_regenerate_only_regenerates_stale_tasks() -> None:
    """Pause-diverted (fresh) tasks must not be needlessly regenerated."""
    worker, submitted = _make_worker()
    stale = _FakeTask(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    fresh = _FakeTask(created=PARAM_UPDATE_TS + timedelta(seconds=10))
    worker._outdated_tasks.put(stale)
    worker._outdated_tasks.put(fresh)

    generate = _run_regenerate(worker, JobRunStatus.PROCESSING)

    assert generate.call_count == 1
    assert len(submitted) == NUM_TASKS
    assert stale.sequence_json == "REGENERATED"
    assert fresh.sequence_json == "ORIGINAL"


def test_regenerate_stops_when_paused() -> None:
    """Draining must stop without feeding a paused hardware worker."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))

    generate = _run_regenerate(worker, JobRunStatus.PAUSED)

    assert submitted == []
    assert generate.call_count == 0
    assert worker._outdated_tasks.qsize() == NUM_TASKS


def test_regenerate_does_not_regenerate_realtime_tasks() -> None:
    """Realtime tasks keep their last-generated sequence, never the generic regen."""
    worker, submitted = _make_worker()
    stale = _FakeTask(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    worker._outdated_tasks.put(stale)

    generate = _run_regenerate(worker, JobRunStatus.PROCESSING, realtime=True)

    assert generate.call_count == 0
    assert submitted == [stale]
    assert stale.sequence_json == "ORIGINAL"


def test_regenerate_drops_cancelled_tasks() -> None:
    """Cancelled jobs' tasks are accounted for directly, not bounced through HW."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))

    generate = _run_regenerate(worker, JobRunStatus.CANCELLED)

    assert submitted == []
    assert generate.call_count == 0
    assert worker._processed_data_points.qsize() == NUM_TASKS
    assert worker._outdated_tasks.qsize() == 0


def test_regenerate_uses_updated_parameters_after_pause() -> None:
    """A parameter changed during a pause is applied when a stale task is regenerated."""
    worker, submitted = _make_worker()
    worker._parameter_dict = {"freq": UPDATED_FREQ}
    stale = _FakeTask(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    worker._outdated_tasks.put(stale)

    generate = _run_regenerate(worker, JobRunStatus.PROCESSING)

    assert submitted == [stale]
    assert stale.sequence_json == "REGENERATED"
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
        _FakeTask(created=PARAM_UPDATE_TS - timedelta(seconds=10), realtime=True)
    )

    for _ in range(MAX_ROUNDS):
        submitted.clear()
        _run_regenerate(worker, JobRunStatus.PROCESSING, realtime=True)
        # Model the hardware worker: divert each resubmission it still finds outdated.
        for task in submitted:
            if should_divert_task(task, PARAM_UPDATE_TS, JobRunStatus.PROCESSING):
                worker._outdated_tasks.put(task)
        if worker._outdated_tasks.empty():
            break

    assert worker._outdated_tasks.empty()
