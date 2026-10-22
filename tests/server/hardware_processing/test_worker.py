from __future__ import annotations

import queue
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from icon.server.data_access.experiment_data import HardwareProcessingError, Readouts
from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.models.sqlite import Job, JobRun
from icon.server.hardware_processing import worker as worker_module
from icon.server.hardware_processing.hardware_controller import HardwareController
from icon.server.hardware_processing.rpc.errors import RPCResponseError
from icon.server.hardware_processing.rpc.gateway import GatewayError
from icon.server.hardware_processing.worker import HardwareProcessingWorker
from icon.server.pre_processing.task import PreProcessingTask

if TYPE_CHECKING:
    from icon.server.post_processing.task import PostProcessingTask

RUN_ID = 7
DATA_POINT_INDEX = 4
HARDWARE_INSTRUCTIONS = [("main", '{"main": "..."}'), ("sub", '{"sub": "..."}')]
EMPTY_READOUTS = Readouts(result_channels={}, vector_channels={}, shot_channels={})


class _SingleTaskQueue:
    """Hands out one task, then stops the worker loop."""

    def __init__(self, task: Any) -> None:
        self._tasks = [task]

    def get(self) -> Any:
        if not self._tasks:
            # Caught by the worker's handle_keyboard_interrupt decorator.
            raise KeyboardInterrupt
        return self._tasks.pop()


class _FakeController(HardwareController):
    def __init__(
        self,
        result: float,
        *,
        send_error: Exception | None = None,
        receive_error: Exception | None = None,
    ) -> None:
        self._readouts = Readouts(
            result_channels={"a": result}, vector_channels={}, shot_channels={}
        )
        self._send_error = send_error
        self._receive_error = receive_error
        self.sent: list[str] = []
        self.ran = False

    def send(self, data: str) -> None:
        if self._send_error is not None:
            raise self._send_error
        self.sent.append(data)

    def run(self) -> None:
        self.ran = True

    def receive(self) -> Readouts:
        if self._receive_error is not None:
            raise self._receive_error
        return self._readouts


def _hardware_task() -> Any:
    pre_processing_task = PreProcessingTask(
        job=Job(id=3),
        job_run=JobRun(id=RUN_ID),
        priority=0,
        local_parameters_timestamp="2026-01-01T00:00:00",
        scan_parameters=[],
        auto_calibration=False,
    )
    return SimpleNamespace(
        pre_processing_task=pre_processing_task,
        priority=0,
        data_point_index=DATA_POINT_INDEX,
        scanned_params={},
        hardware_instructions=HARDWARE_INSTRUCTIONS,
        src_dir=None,
        created=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scan_progress=MagicMock(),
        outdated_tasks=queue.Queue(),
    )


def _run_worker(
    monkeypatch: pytest.MonkeyPatch, controllers: dict[str, _FakeController]
) -> tuple[list[PostProcessingTask], MagicMock, list[int]]:
    """Run the worker on one task.

    Returns:
        The emitted post-processing tasks, the run-update mock, and the number of
        post-processing tasks queued at the time of each run update.
    """
    post_processing_queue: queue.Queue[PostProcessingTask] = queue.Queue()
    queued_at_update: list[int] = []
    update_run = MagicMock(
        side_effect=lambda **_: queued_at_update.append(post_processing_queue.qsize())
    )
    monkeypatch.setattr(
        worker_module.DeviceRepository, "get_devices_by_status", lambda **_: []
    )
    monkeypatch.setattr(
        worker_module.JobRunRepository,
        "get_run_by_job_id",
        lambda **_: SimpleNamespace(
            status=JobRunStatus.PROCESSING, parameter_update_timestamp=None
        ),
    )
    monkeypatch.setattr(worker_module, "try_update_run_by_id", update_run)

    worker = HardwareProcessingWorker.__new__(HardwareProcessingWorker)
    worker._queue = _SingleTaskQueue(_hardware_task())  # type: ignore[assignment]
    worker._post_processing_queue = post_processing_queue  # type: ignore[assignment]
    worker._devices = {  # type: ignore[assignment]
        device_id: SimpleNamespace(controller=controller)
        for device_id, controller in controllers.items()
    }
    worker._executor = None
    worker._executor_size = 0
    worker._main_device_start_delay = 0.0
    worker.run()

    return list(post_processing_queue.queue), update_run, queued_at_update


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (RPCResponseError(1, [0, "Sequence too long"]), "Sequence too long"),
        (GatewayError("the task was aborted"), "the task was aborted"),
        # The device locked up
        (
            TimeoutError("no response to exp.StartTask within 5s"),
            "no response to exp.StartTask within 5s",
        ),
    ],
)
def test_run_error_emits_hardware_instructions_before_failing_job(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    controllers = {
        "main": _FakeController(1.0, receive_error=error),
        "sub": _FakeController(2.0),
    }
    tasks, update_run, queued_at_update = _run_worker(monkeypatch, controllers)

    assert len(tasks) == 1
    data_point = tasks[0].data_point
    assert data_point.index == DATA_POINT_INDEX
    assert data_point.failed
    assert [
        (d.device_id, d.hardware_instructions) for d in data_point.device_data
    ] == HARDWARE_INSTRUCTIONS
    assert [d.readouts for d in data_point.device_data] == [
        HardwareProcessingError(message=message),
        controllers["sub"].receive(),
    ]

    update_run.assert_called_once_with(
        run_id=RUN_ID, status=JobRunStatus.FAILED, log=f"main: {message}"
    )
    # The post-processing task is queued before the job is marked as failed.
    assert queued_at_update == [1]


def test_job_log_names_every_failed_device(monkeypatch: pytest.MonkeyPatch) -> None:
    controllers = {
        "main": _FakeController(
            1.0, receive_error=TimeoutError("no response to runExperiment within 5s")
        ),
        "sub": _FakeController(
            2.0, receive_error=TimeoutError("no response to exp.StartTask within 5s")
        ),
    }
    _, update_run, _ = _run_worker(monkeypatch, controllers)

    update_run.assert_called_once_with(
        run_id=RUN_ID,
        status=JobRunStatus.FAILED,
        log="main: no response to runExperiment within 5s\n"
        "sub: no response to exp.StartTask within 5s",
    )


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (RPCResponseError(1, [0, "Invalid sequence"]), "Invalid sequence"),
        (
            GatewayError("Submitted sequence is not valid JSON. Can't run"),
            "Submitted sequence is not valid JSON. Can't run",
        ),
        (
            RuntimeError("Could not connect to the Zedboard"),
            "Could not connect to the Zedboard",
        ),
    ],
)
def test_send_error_emits_hardware_instructions_without_running(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    controllers = {
        "main": _FakeController(1.0),
        "sub": _FakeController(2.0, send_error=error),
    }
    tasks, update_run, _ = _run_worker(monkeypatch, controllers)

    assert not any(controller.ran for controller in controllers.values())
    assert len(tasks) == 1
    assert [d.readouts for d in tasks[0].data_point.device_data] == [
        EMPTY_READOUTS,
        HardwareProcessingError(message=message),
    ]
    update_run.assert_called_once_with(
        run_id=RUN_ID, status=JobRunStatus.FAILED, log=f"sub: {message}"
    )


def test_errors_before_sending_only_fail_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # "sub" is missing, e.g. because it was disabled
    controllers = {"main": _FakeController(1.0)}
    tasks, update_run, _ = _run_worker(monkeypatch, controllers)

    assert tasks == []
    assert controllers["main"].sent == []
    update_run.assert_called_once_with(
        run_id=RUN_ID,
        status=JobRunStatus.FAILED,
        log="No such device: 'sub' (the device might have been disabled)",
    )


def test_successful_run_emits_readouts(monkeypatch: pytest.MonkeyPatch) -> None:
    controllers = {"main": _FakeController(1.0), "sub": _FakeController(2.0)}
    tasks, update_run, _ = _run_worker(monkeypatch, controllers)

    assert len(tasks) == 1
    data_point = tasks[0].data_point
    assert not data_point.failed
    assert [d.readouts for d in data_point.device_data] == [
        controllers["main"].receive(),
        controllers["sub"].receive(),
    ]
    assert controllers["main"].sent == [HARDWARE_INSTRUCTIONS[0][1]]
    update_run.assert_not_called()
