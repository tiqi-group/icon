"""Tests for the hardware processing worker."""

import multiprocessing
import queue
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pydase.units as u
import pytest
from pydase.utils.serialization.serializer import dump

from icon.server.data_access.experiment_data import HardwareProcessingError, Readouts
from icon.server.data_access.models.enums import DeviceStatus, JobRunStatus
from icon.server.data_access.models.sqlite import Job, JobRun
from icon.server.data_access.models.sqlite.device import Device
from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter
from icon.server.hardware_processing import worker as worker_module
from icon.server.hardware_processing.hardware_controller import HardwareController
from icon.server.hardware_processing.rpc.errors import RPCResponseError
from icon.server.hardware_processing.worker import HardwareProcessingWorker
from icon.server.post_processing.task import PostProcessingTask
from icon.server.pre_processing.task import PreProcessingTask

RUN_ID = 7
DATA_POINT_INDEX = 4
HARDWARE_INSTRUCTIONS = [("main", '{"main": "..."}'), ("sub", '{"sub": "..."}')]
EMPTY_READOUTS = Readouts(result_channels={}, vector_channels={}, shot_channels={})
ACTIVE_RUN_STATUSES = (JobRunStatus.PROCESSING, JobRunStatus.PAUSED)


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


def test_run_error_emits_hardware_instructions_before_failing_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = RPCResponseError(1, [0, "Sequence too long"])
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
        HardwareProcessingError(message="Sequence too long"),
        controllers["sub"].receive(),
    ]

    update_run.assert_called_once_with(
        run_id=RUN_ID,
        status=JobRunStatus.FAILED,
        log="DeviceError ('main') Sequence too long",
        only_if_status=ACTIVE_RUN_STATUSES,
    )
    # The post-processing task is queued before the job is marked as failed.
    assert queued_at_update == [1]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (RPCResponseError(1, [0, "Invalid sequence"]), "Invalid sequence"),
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
        run_id=RUN_ID,
        status=JobRunStatus.FAILED,
        log=f"DeviceError ('sub') {message}",
        only_if_status=ACTIVE_RUN_STATUSES,
    )


def test_errors_of_every_device_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    # The main device fails and never triggers the subordinate one, which times out.
    controllers = {
        "main": _FakeController(
            1.0, receive_error=RPCResponseError(1, [0, "Sequence too long"])
        ),
        "sub": _FakeController(2.0, receive_error=TimeoutError("No response")),
    }
    tasks, update_run, _ = _run_worker(monkeypatch, controllers)

    assert len(tasks) == 1
    assert [d.readouts for d in tasks[0].data_point.device_data] == [
        HardwareProcessingError(message="Sequence too long"),
        HardwareProcessingError(message="No response"),
    ]
    update_run.assert_called_once_with(
        run_id=RUN_ID,
        status=JobRunStatus.FAILED,
        log="DeviceError ('main') Sequence too long; DeviceError ('sub') No response",
        only_if_status=ACTIVE_RUN_STATUSES,
    )


def test_other_errors_only_fail_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_to_set_values(*_: Any, **__: Any) -> None:
        raise RuntimeError("Failed to set 'x' of device 'pydase_service'")

    monkeypatch.setattr(
        HardwareProcessingWorker, "_set_pydase_service_values", fail_to_set_values
    )
    controllers = {"main": _FakeController(1.0), "sub": _FakeController(2.0)}
    tasks, update_run, _ = _run_worker(monkeypatch, controllers)

    assert tasks == []
    assert not any(controller.sent for controller in controllers.values())
    update_run.assert_called_once_with(
        run_id=RUN_ID,
        status=JobRunStatus.FAILED,
        log="Failed to set 'x' of device 'pydase_service'",
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


def _make_worker() -> HardwareProcessingWorker:
    return HardwareProcessingWorker(
        hardware_processing_queue=queue.PriorityQueue(),
        post_processing_queue=multiprocessing.Queue(),
        manager=MagicMock(),
        devices=MagicMock(),
    )


def _fake_task(*, scan_parameters: list[Any], scanned_params: dict[str, Any]) -> Any:
    """Minimal stand-in for HardwareProcessingTask (only the attributes touched)."""
    return SimpleNamespace(
        scanned_params=scanned_params,
        pre_processing_task=SimpleNamespace(scan_parameters=scan_parameters),
    )


def _enabled_device() -> Any:
    return SimpleNamespace(
        name="RFSoC",
        url="http://rfsoc.example",
        status=DeviceStatus.ENABLED,
        retry_attempts=1,
        retry_delay_seconds=0.0,
    )


@contextmanager
def patch_client_calls(get_value_response: Any) -> Iterator[Any]:
    """Patch the device lookup and the pydase client calls."""
    call = MagicMock(side_effect=[None, get_value_response])
    with (
        patch(
            "icon.server.hardware_processing.worker.DeviceRepository.get_device_by_name",
            return_value=_enabled_device(),
        ),
        patch("icon.server.hardware_processing.worker.pydase.Client"),
        patch(
            "icon.server.hardware_processing.worker.client_call_with_timeout",
            call,
        ),
    ):
        yield call


def test_set_pydase_service_values_reattaches_unit() -> None:
    """A flattened device scan value is sent back to the device as a Quantity."""
    worker = _make_worker()
    voltage = u.convert_to_quantity(1.0, "V")
    task = _fake_task(
        scan_parameters=[
            ScanParameter(
                name="Voltage",
                variable_id="voltage",
                scan_values=[voltage],
                device=Device(
                    name="RFSoC",
                    url="http://rfsoc.example",
                ),
            )
        ],
        scanned_params={"Device(RFSoC) voltage": voltage.magnitude},
    )

    with patch_client_calls(get_value_response=voltage) as call:
        worker._set_pydase_service_values(task)

    update_call = call.call_args_list[0]
    assert update_call.kwargs["event"] == "update_value"
    assert update_call.kwargs["data"]["value"] == dump(voltage)
    # The verification comparison must not report a mismatch (Quantity == Quantity).
    assert call.call_args_list[1].kwargs["event"] == "get_value"
    expected_call_count = 2
    assert call.call_count == expected_call_count


def test_set_pydase_service_values_keeps_plain_values() -> None:
    """Scans without a persisted unit keep sending plain values to the device."""
    worker = _make_worker()
    task = _fake_task(
        scan_parameters=[
            ScanParameter(
                name="Voltage",
                variable_id="voltage",
                scan_values=[1.0, 2.0],
            )
        ],
        scanned_params={"Device(RFSoC) voltage": 1.5},
    )

    with patch_client_calls(get_value_response=1.5) as call:
        worker._set_pydase_service_values(task)

    update_call = call.call_args_list[0]
    assert update_call.kwargs["event"] == "update_value"
    assert update_call.kwargs["data"]["value"] == dump(1.5)
    expected_call_count = 2
    assert call.call_count == expected_call_count


def test_set_pydase_service_values_ignores_non_device_params() -> None:
    """Non-device (shared) parameters are not pushed to any device service."""
    worker = _make_worker()
    task = _fake_task(
        scan_parameters=[
            ScanParameter(
                name="Frequency",
                variable_id="frequency",
                scan_values=[u.convert_to_quantity(100.0, "MHz")],
            )
        ],
        scanned_params={"frequency": 100.0},
    )

    with patch_client_calls(get_value_response=None) as call:
        worker._set_pydase_service_values(task)

    assert call.call_count == 0
