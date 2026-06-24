import queue
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from icon.server.data_access.models.enums import JobRunStatus
from icon.server.pre_processing.worker import PreProcessingWorker

# Fixed reference point: the parameter-update timestamp the consumer compares against.
PARAM_UPDATE_TS = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
NUM_TASKS = 2  # tasks placed in the queue per test
UPDATED_FREQ = 2.0  # parameter value after a calibration during a pause


class _FakeTask:
    """Minimal stand-in for HardwareProcessingTask (only the attributes touched)."""

    def __init__(self, created: datetime, sequence_json: str = "ORIGINAL") -> None:
        self.created = created
        self.priority = 0
        self.scanned_params: dict = {}
        self.sequence_json = sequence_json
        self.pre_processing_task = SimpleNamespace(
            job=SimpleNamespace(number_of_shots=100)
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


def _pre_processing_task() -> SimpleNamespace:
    return SimpleNamespace(
        job=SimpleNamespace(id=1, scan_parameters=[]),
        job_run=SimpleNamespace(id=1),
    )


def _run_mock(status: JobRunStatus) -> MagicMock:
    # SQLite returns this column without timezone info (stored as UTC), so mirror that.
    return MagicMock(
        status=status,
        parameter_update_timestamp=PARAM_UPDATE_TS.replace(tzinfo=None),
    )


def test_regenerate_only_regenerates_stale_tasks() -> None:
    """Pause-diverted (fresh) tasks must not be needlessly regenerated."""
    worker, submitted = _make_worker()
    stale = _FakeTask(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    fresh = _FakeTask(created=PARAM_UPDATE_TS + timedelta(seconds=10))
    worker._outdated_tasks.put(stale)
    worker._outdated_tasks.put(fresh)

    with (
        patch(
            "icon.server.pre_processing.worker.generate_sequence_json",
            return_value="REGENERATED",
        ) as generate,
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
    ):
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.PROCESSING)
        worker._regenerate_outdated_jobs(
            client=object(),
            pre_processing_task=_pre_processing_task(),
            namespace=object(),
        )

    assert generate.call_count == 1
    assert len(submitted) == NUM_TASKS
    assert stale.sequence_json == "REGENERATED"
    assert fresh.sequence_json == "ORIGINAL"


def test_regenerate_stops_when_paused() -> None:
    """Draining must stop without feeding a paused hardware worker."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))

    with (
        patch("icon.server.pre_processing.worker.generate_sequence_json") as generate,
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
    ):
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.PAUSED)
        worker._regenerate_outdated_jobs(
            client=object(),
            pre_processing_task=_pre_processing_task(),
            namespace=object(),
        )

    assert submitted == []
    assert generate.call_count == 0
    assert worker._outdated_tasks.qsize() == NUM_TASKS


def test_regenerate_does_not_regenerate_realtime_tasks() -> None:
    """Realtime tasks keep their last-generated sequence, never the generic regen."""
    worker, submitted = _make_worker()
    stale = _FakeTask(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    worker._outdated_tasks.put(stale)

    with (
        patch("icon.server.pre_processing.worker.generate_sequence_json") as generate,
        patch(
            "icon.server.pre_processing.worker.contains_realtime_parameter",
            return_value=True,
        ),
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
    ):
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.PROCESSING)
        worker._regenerate_outdated_jobs(
            client=object(),
            pre_processing_task=_pre_processing_task(),
            namespace=object(),
        )

    assert generate.call_count == 0
    assert submitted == [stale]
    assert stale.sequence_json == "ORIGINAL"


def test_regenerate_drops_cancelled_tasks() -> None:
    """Cancelled jobs' tasks are accounted for directly, not bounced through HW."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))

    with (
        patch("icon.server.pre_processing.worker.generate_sequence_json") as generate,
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
    ):
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.CANCELLED)
        worker._regenerate_outdated_jobs(
            client=object(),
            pre_processing_task=_pre_processing_task(),
            namespace=object(),
        )

    assert submitted == []
    assert generate.call_count == 0
    assert worker._processed_data_points.qsize() == NUM_TASKS
    assert worker._outdated_tasks.qsize() == 0


def test_regenerate_uses_updated_parameters_after_pause() -> None:
    """A parameter changed during a pause is applied when a stale task is regenerated."""
    worker, submitted = _make_worker()
    worker._parameter_dict = {"freq": UPDATED_FREQ}
    # Built before the parameter update -> stale -> regenerated with the new value.
    stale = _FakeTask(created=PARAM_UPDATE_TS - timedelta(seconds=10))
    worker._outdated_tasks.put(stale)

    with (
        patch(
            "icon.server.pre_processing.worker.generate_sequence_json",
            return_value="REGENERATED",
        ) as generate,
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
    ):
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.PROCESSING)
        worker._regenerate_outdated_jobs(
            client=object(),
            pre_processing_task=_pre_processing_task(),
            namespace=object(),
        )

    assert submitted == [stale]
    assert stale.sequence_json == "REGENERATED"
    assert generate.call_args.kwargs["parameter_dict"]["freq"] == UPDATED_FREQ
