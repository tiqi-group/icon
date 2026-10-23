"""Tests for the hardware processing worker."""

import multiprocessing
import queue
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pydase.units as u
from pydase.utils.serialization.serializer import dump

from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.models.sqlite.device import Device
from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter
from icon.server.hardware_processing.worker import HardwareProcessingWorker


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
