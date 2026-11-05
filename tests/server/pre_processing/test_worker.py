from __future__ import annotations

import dataclasses
import queue
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import pytest

from icon.server.data_access.models.enums import JobRunStatus
from icon.server.pre_processing.arbiter import Arbiter, TaskQueue
from icon.server.pre_processing.worker import (
    ExperimentIdentifier,
    PreProcessingWorker,
    consume_queue,
    create_hardware_instructions,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

# Fixed reference point: the parameter-update timestamp tasks are compared against.
PARAM_UPDATE_TS = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
STALE_TS = PARAM_UPDATE_TS - timedelta(seconds=10)
RUN_ID = 1  # the job run the worker is currently scanning
DEVICE_ORDER = ["main", "sub"]  # the job run's device order, loaded when it starts
TASK_QUEUE_SIZE = 6  # tasks the worker keeps queued for the hardware worker
NUM_DATA_POINTS = 10  # data points of the regular scan
REALTIME_GENERATIONS = 2  # instructions generated in the realtime scan test


@dataclasses.dataclass
class _FakeTask:
    """Minimal stand-in for HardwareProcessingTask (only the attributes touched)."""

    data_point_index: int
    scanned_params: dict[str, Any]
    pre_processing_task: Any
    created: datetime = STALE_TS
    priority: int = 0
    hardware_instructions: Any = None
    global_parameter_timestamp: datetime = STALE_TS

    def model_copy(self, *, update: dict[str, Any]) -> _FakeTask:
        return dataclasses.replace(self, **update)


def _fake_task(index: int, *, run_id: int = RUN_ID) -> Any:
    return _FakeTask(
        data_point_index=index,
        scanned_params={"x": index},
        pre_processing_task=SimpleNamespace(job_run=SimpleNamespace(id=run_id)),
    )


def _pre_processing_task(**job: Any) -> Any:
    return SimpleNamespace(
        job=SimpleNamespace(id=1, number_of_shots=100, **job),
        job_run=SimpleNamespace(id=RUN_ID),
    )


def _make_worker(task_queue_size: int = TASK_QUEUE_SIZE) -> PreProcessingWorker:
    task_queue = TaskQueue(Arbiter(), 0, size=task_queue_size)
    # As the worker does when it picks up the job run
    task_queue.start_run(RUN_ID)
    return PreProcessingWorker(
        worker_number=0,
        pre_processing_queue=queue.PriorityQueue(),
        update_queue=cast("Any", queue.Queue()),
        task_queue=task_queue,
        manager=MagicMock(),
        experiment_library_client=MagicMock(),
    )


def _queued_tasks(task_queue: TaskQueue) -> list[Any]:
    """Pull the queued tasks that are not held, as the hardware worker does."""
    arbiter = task_queue._arbiter
    tasks = []
    while arbiter._next_worker() is not None:
        tasks.append(arbiter.pull())
    return tasks


def _hand_over_tasks(task_queue: TaskQueue) -> list[Any]:
    """Model the hardware worker pulling and finishing every queued task."""
    tasks = _queued_tasks(task_queue)
    for task in tasks:
        task_queue._arbiter.mark_finished(task.pre_processing_task.job_run.id)
    return tasks


def _run_mock(status: JobRunStatus) -> MagicMock:
    return MagicMock(status=status)


def _set_parameter_update_timestamp(worker: PreProcessingWorker) -> Any:
    """Stand-in for _update_parameter_dict, which sets the parameter timestamp."""

    def update_parameter_dict(*_: Any, **__: Any) -> None:
        worker._global_parameter_timestamp = datetime.now(timezone.utc)

    return patch.object(
        worker, "_update_parameter_dict", side_effect=update_parameter_dict
    )


def _handle_parameter_update(
    worker: PreProcessingWorker, update: dict[str, Any]
) -> MagicMock:
    """Handle one update event; return the parameter-dict update mock."""
    worker._update_queue.put(cast("Any", update))
    with _set_parameter_update_timestamp(worker) as update_mock:
        worker._handle_parameter_updates(
            _pre_processing_task(), namespace=cast("Any", object())
        )
    return update_mock


def test_parameter_update_takes_back_the_runs_tasks() -> None:
    """Their data points are prepared again first."""
    worker = _make_worker()
    for task in (_fake_task(1), _fake_task(3)):
        worker._task_queue.put(task)
    worker._data_points_to_process.put((2, {"x": 2}))

    update = _handle_parameter_update(worker, {"event": "update_parameters"})

    assert update.call_count == 1
    assert _queued_tasks(worker._task_queue) == []
    assert list(consume_queue(worker._data_points_to_process)) == [
        (1, {"x": 1}),
        (2, {"x": 2}),
        (3, {"x": 3}),
    ]


def test_ignored_parameter_update_keeps_the_tasks() -> None:
    worker = _make_worker()
    worker._task_queue.put(_fake_task(0))

    update = _handle_parameter_update(
        worker, {"event": "update_parameters", "job_id": 2}
    )

    assert update.call_count == 0
    assert len(_queued_tasks(worker._task_queue)) == 1


def _wait_while_paused(
    worker: PreProcessingWorker, statuses: list[JobRunStatus], on_sleep: Any
) -> Any:
    with (
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
        patch("icon.server.pre_processing.worker.time.sleep", side_effect=on_sleep),
        _set_parameter_update_timestamp(worker),
    ):
        repo.get_run_by_job_id.side_effect = [_run_mock(s) for s in statuses]
        return worker._wait_while_paused(
            _pre_processing_task(), namespace=cast("Any", object())
        )


def test_pause_keeps_the_tasks() -> None:
    """The worker waits for the resume; the tasks run as they are then."""
    worker = _make_worker()
    worker._task_queue.put(_fake_task(0))
    worker._task_queue.put(_fake_task(1))
    sleeps: list[Any] = []

    job_run = _wait_while_paused(
        worker,
        [JobRunStatus.PAUSED, JobRunStatus.PAUSED, JobRunStatus.PROCESSING],
        on_sleep=sleeps.append,
    )

    assert job_run.status == JobRunStatus.PROCESSING
    assert len(sleeps) == 2  # noqa: PLR2004
    assert [task.data_point_index for task in _queued_tasks(worker._task_queue)] == [
        0,
        1,
    ]
    assert worker._data_points_to_process.empty()


@pytest.mark.parametrize("failing", [False, True])
def test_job_run_is_started_and_ended_in_the_task_queue(*, failing: bool) -> None:
    """Its finished tasks are counted from zero, also if its ID was used before.

    Ending it empties the task queue for the next job run, also of a job run that failed
    or was cancelled while paused, and forgets its hold.
    """
    worker = _make_worker()
    arbiter = worker._task_queue._arbiter
    arbiter.mark_finished(RUN_ID)
    finished_at_start: list[int] = []

    def process_task(*_: Any, **__: Any) -> None:
        finished_at_start.append(worker._task_queue.finished(RUN_ID))
        arbiter.hold(RUN_ID)
        worker._task_queue.put(_fake_task(0))
        if failing:
            raise RuntimeError("failed")

    worker._queue = MagicMock()
    worker._queue.get.side_effect = [
        _pre_processing_task(experiment_source_id=1),
        KeyboardInterrupt,
    ]

    with (
        patch.object(worker, "_process_task", side_effect=process_task),
        patch("icon.server.pre_processing.worker.JobRunRepository"),
        patch("icon.server.pre_processing.worker.try_update_run_by_id"),
        patch("icon.server.pre_processing.worker.JobRepository"),
        patch("icon.server.pre_processing.worker.try_auto_fit"),
    ):
        worker.run()

    assert finished_at_start == [0]
    assert not arbiter._tasks[0]
    assert not arbiter._held
    assert not arbiter._finished


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError("queue is gone")])
def test_worker_stops_its_venv_calls_on_exit(error: BaseException) -> None:
    worker = _make_worker()
    worker._queue = MagicMock()
    worker._queue.get.side_effect = error

    with (
        patch("icon.server.pre_processing.worker.venv_exec.shutdown") as shutdown,
        pytest.raises(OSError, match="queue is gone")
        if isinstance(error, OSError)
        else nullcontext(),
    ):
        worker.run()

    shutdown.assert_called_once_with()


def test_parameter_update_while_paused_takes_back_the_tasks() -> None:
    worker = _make_worker()
    worker._task_queue.put(_fake_task(0))

    _wait_while_paused(
        worker,
        [JobRunStatus.PAUSED, JobRunStatus.PAUSED, JobRunStatus.PROCESSING],
        on_sleep=lambda _: worker._update_queue.put(
            cast("Any", {"event": "update_parameters"})
        ),
    )

    assert _queued_tasks(worker._task_queue) == []
    assert list(consume_queue(worker._data_points_to_process)) == [(0, {"x": 0})]


def test_cancelled_regular_scan_drops_its_tasks() -> None:
    worker = _make_worker()
    worker._task_queue.put(_fake_task(0))
    scan_parameter = SimpleNamespace(
        realtime=False, unique_id=lambda: "x", scan_values=[0]
    )

    with patch("icon.server.pre_processing.worker.JobRunRepository") as repo:
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.CANCELLED)
        worker._handle_regular_scan(
            _pre_processing_task(repetitions=1, scan_parameters=[scan_parameter]),
            namespace=cast("Any", object()),
            client=cast("Any", object()),
            src_dir=None,
        )

    assert _queued_tasks(worker._task_queue) == []


def _create_task(worker: PreProcessingWorker) -> Any:
    """Stand-in for _create_hardware_task."""

    def create_task(**kwargs: Any) -> _FakeTask:
        return _FakeTask(
            data_point_index=kwargs["index"],
            scanned_params=kwargs["data_point"],
            pre_processing_task=kwargs["pre_processing_task"],
            created=datetime.now(timezone.utc),
            hardware_instructions=kwargs["hardware_instructions"],
            global_parameter_timestamp=worker._global_parameter_timestamp,
        )

    return patch.object(worker, "_create_hardware_task", side_effect=create_task)


def test_regular_scan_fills_the_task_queue_in_data_point_order() -> None:
    """Instructions are generated as far as the task queue has room."""
    worker = _make_worker()
    worker._global_parameter_timestamp = STALE_TS
    queued_at_generation: list[int] = []
    handed_over: list[Any] = []

    def generate(
        _client: Any, *, parameter_dict: dict[str, Any], **_: Any
    ) -> list[tuple[str, str]]:
        queued_at_generation.append(len(worker._task_queue._arbiter._tasks[0]))
        return [("main", str(parameter_dict["x"]))]

    wait_for_space = worker._task_queue.wait_for_space

    def hand_over_if_full(timeout: float) -> bool:
        # Model the hardware worker pulling the queued tasks once the queue is full.
        if not wait_for_space(timeout=0):
            handed_over.extend(_hand_over_tasks(worker._task_queue))
        return wait_for_space(timeout=timeout)

    scan_parameter = SimpleNamespace(
        realtime=False, unique_id=lambda: "x", scan_values=list(range(NUM_DATA_POINTS))
    )
    with (
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
        patch(
            "icon.server.pre_processing.worker.time.sleep",
            side_effect=lambda _: handed_over.extend(
                _hand_over_tasks(worker._task_queue)
            ),
        ),
        patch(
            "icon.server.pre_processing.worker.create_hardware_instructions",
            side_effect=generate,
        ),
        patch.object(worker._task_queue, "wait_for_space", hand_over_if_full),
        _create_task(worker),
    ):
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.PROCESSING)
        worker._handle_regular_scan(
            _pre_processing_task(repetitions=1, scan_parameters=[scan_parameter]),
            namespace=cast("Any", object()),
            client=cast("Any", object()),
            src_dir=None,
        )

    assert max(queued_at_generation) == TASK_QUEUE_SIZE - 1
    assert [task.data_point_index for task in handed_over] == list(
        range(NUM_DATA_POINTS)
    )
    assert [task.hardware_instructions for task in handed_over] == [
        [("main", str(x))] for x in range(NUM_DATA_POINTS)
    ]


def _run_realtime_scan(
    worker: PreProcessingWorker, wait_for_space: Any, handed_over: list[Any]
) -> MagicMock:
    """Scan a realtime parameter with two values; return the generate mock.

    Whenever the worker waits for the scan's last data points, the hardware worker is
    modelled to run the queued tasks, which are added to ``handed_over``.
    """
    realtime_parameter = SimpleNamespace(realtime=True, scan_values=[0.0, 1.0])
    with (
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
        patch(
            "icon.server.pre_processing.worker.time.sleep",
            side_effect=lambda _: handed_over.extend(
                _hand_over_tasks(worker._task_queue)
            ),
        ),
        patch(
            "icon.server.pre_processing.worker.create_hardware_instructions"
        ) as generate,
        patch.object(worker._task_queue, "wait_for_space", wait_for_space),
        _create_task(worker),
        _set_parameter_update_timestamp(worker),
    ):
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.PROCESSING)
        worker._handle_realtime_scan(
            _pre_processing_task(repetitions=1, scan_parameters=[realtime_parameter]),
            namespace=cast("Any", object()),
            client=cast("Any", object()),
            src_dir=None,
        )
    return generate


def test_realtime_scan_prepares_taken_back_data_points_first() -> None:
    """A parameter update while the task queue is full regenerates the queued data point."""
    worker = _make_worker(task_queue_size=1)
    worker._global_parameter_timestamp = STALE_TS
    wait_for_space = worker._task_queue.wait_for_space
    waits = 0
    handed_over: list[Any] = []

    def update_then_hand_over(timeout: float) -> bool:
        nonlocal waits
        if not wait_for_space(timeout=0):
            waits += 1
            if waits == 1:
                # The parameters change while the first data point waits in the queue.
                worker._update_queue.put(cast("Any", {"event": "update_parameters"}))
                return False
            handed_over.extend(_hand_over_tasks(worker._task_queue))
        return wait_for_space(timeout=timeout)

    generate = _run_realtime_scan(worker, update_then_hand_over, handed_over)

    assert [task.data_point_index for task in handed_over] == [0, 1]
    # The first data point is generated twice, the second reuses its instructions.
    assert generate.call_count == REALTIME_GENERATIONS


def test_realtime_scan_queues_copies_of_reused_tasks() -> None:
    """Reusing a data point's instructions doesn't change its task still queued."""
    worker = _make_worker()
    worker._global_parameter_timestamp = STALE_TS
    handed_over: list[Any] = []

    generate = _run_realtime_scan(
        worker, worker._task_queue.wait_for_space, handed_over
    )

    assert generate.call_count == 1
    assert [task.data_point_index for task in handed_over] == [0, 1]


def test_realtime_scan_ends_once_its_data_points_ran() -> None:
    """So the worker only takes the next job run with an empty task queue."""
    worker = _make_worker()
    worker._global_parameter_timestamp = STALE_TS
    handed_over: list[Any] = []

    _run_realtime_scan(worker, worker._task_queue.wait_for_space, handed_over)

    assert len(handed_over) == worker._task_queue.finished(RUN_ID) == 2  # noqa: PLR2004
    assert not worker._task_queue._arbiter._tasks[0]


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


class _RecordingClient:
    """Library client recording its calls and when the library is kept loaded."""

    def __init__(self, *, failing: bool = False) -> None:
        self.events: list[str] = []
        self._failing = failing

    def checkout_revision(self, revision: str | None) -> str:  # noqa: ARG002
        self.events.append("checkout_revision")
        return "src"

    @contextmanager
    def pinned(self) -> Iterator[None]:
        self.events.append("enter pinned")
        try:
            yield
        finally:
            self.events.append("exit pinned")

    @contextmanager
    def reuse_venv(self) -> Iterator[None]:
        self.events.append("enter reuse_venv")
        try:
            yield
        finally:
            self.events.append("exit reuse_venv")

    async def get_experiment_readout_metadata(self, **_: Any) -> list[Any]:
        self.events.append("get_experiment_readout_metadata")
        return []

    async def load_device_order(self) -> list[str]:
        self.events.append("load_device_order")
        return DEVICE_ORDER

    async def create_hardware_instructions(self, **_: Any) -> dict[str, str]:
        self.events.append("create_hardware_instructions")
        if self._failing:
            raise RuntimeError("bad sequence")
        return {"main": "main instructions"}


def _process_task(client: _RecordingClient, n_data_points: int) -> None:
    """Run a regular scan of ``n_data_points`` through the worker's job run handling."""
    worker = _make_worker()
    pre_processing_task = SimpleNamespace(
        job=SimpleNamespace(
            id=1,
            number_of_shots=100,
            repetitions=1,
            scan_parameters=[],
            experiment_source=SimpleNamespace(experiment_id="module.Class (instance)"),
        ),
        job_run=SimpleNamespace(id=RUN_ID),
        priority=0,
        debug_mode=False,
        git_commit_hash="abc",
    )
    with (
        patch("icon.server.pre_processing.worker.JobRunRepository") as repo,
        patch("icon.server.pre_processing.worker.ExperimentDataRepository"),
        patch("icon.server.pre_processing.worker.change_process_priority"),
        patch(
            "icon.server.pre_processing.worker.get_scan_combinations",
            return_value=[{}] * n_data_points,
        ),
        patch.object(worker, "_update_parameter_dict"),
        patch.object(worker, "_handle_parameter_updates"),
        patch.object(worker, "_create_hardware_task"),
        # Model the hardware worker, running every queued data point
        patch.object(
            worker._task_queue,
            "put",
            side_effect=lambda task: worker._task_queue._arbiter.mark_finished(RUN_ID),  # noqa: ARG005
        ),
    ):
        repo.get_run_by_job_id.return_value = _run_mock(JobRunStatus.PROCESSING)
        worker._process_task(
            cast("Any", pre_processing_task), isolated_lib_client=cast("Any", client)
        )


def test_job_run_keeps_the_library_loaded_after_the_checkout() -> None:
    client = _RecordingClient()

    _process_task(client, n_data_points=2)

    assert client.events == [
        "enter pinned",
        "checkout_revision",
        "enter reuse_venv",
        "get_experiment_readout_metadata",
        "load_device_order",
        "create_hardware_instructions",
        "create_hardware_instructions",
        "exit reuse_venv",
        "exit pinned",
    ]


def test_failed_job_run_stops_keeping_the_library_loaded() -> None:
    client = _RecordingClient(failing=True)

    with pytest.raises(RuntimeError, match="bad sequence"):
        _process_task(client, n_data_points=2)

    assert client.events[-3:] == [
        "create_hardware_instructions",
        "exit reuse_venv",
        "exit pinned",
    ]
