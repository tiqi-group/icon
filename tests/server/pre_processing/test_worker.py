import queue
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from icon.server.data_access.models.enums import JobRunStatus
from icon.server.pre_processing.worker import PreProcessingWorker

# Fixed reference point: the parameter-update timestamp the consumer compares against.
PARAM_UPDATE_TS = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
NUM_TASKS = 2  # tasks placed in the queue per test


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
    submitted: list[_FakeTask] = []
    worker._submit_task_to_hw_worker = lambda *, task: submitted.append(task)
    return worker, submitted


def _pre_processing_task() -> SimpleNamespace:
    return SimpleNamespace(job=SimpleNamespace(id=1), job_run=SimpleNamespace(id=1))


def test_regenerate_only_regenerates_stale_tasks() -> None:
    """Pause-diverted (fresh) tasks must not be needlessly regenerated (#1)."""
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
        repo.get_parameter_update_timestamp.return_value = PARAM_UPDATE_TS
        repo.get_run_by_job_id.return_value = MagicMock(status=JobRunStatus.PROCESSING)
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
    """Draining must stop without feeding a paused hardware worker (#3)."""
    worker, submitted = _make_worker()
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))
    worker._outdated_tasks.put(_FakeTask(created=PARAM_UPDATE_TS))

    with (
        patch("icon.server.pre_processing.worker.generate_sequence_json") as generate,
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
    ):
        repo.get_parameter_update_timestamp.return_value = PARAM_UPDATE_TS
        repo.get_run_by_job_id.return_value = MagicMock(status=JobRunStatus.PAUSED)
        worker._regenerate_outdated_jobs(
            client=object(),
            pre_processing_task=_pre_processing_task(),
            namespace=object(),
        )

    assert submitted == []
    assert generate.call_count == 0
    assert worker._outdated_tasks.qsize() == NUM_TASKS
