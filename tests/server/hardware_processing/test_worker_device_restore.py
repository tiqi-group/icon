"""Unit tests for scanned-device-parameter capture/restore in the hardware worker.

These exercise the pure capture/restore logic directly on a `HardwareProcessingWorker`
instance without starting the process or touching real devices: the pydase clients are
replaced with an in-memory fake and `DeviceRepository.get_device_by_name` is patched.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from icon.server.data_access.models.enums import DeviceStatus
from icon.server.hardware_processing import worker as worker_module
from icon.server.hardware_processing.worker import HardwareProcessingWorker

PRE_SCAN_VALUE = 1.0
FIRST_SCAN_POINT = 5.0
SECOND_SCAN_POINT = 8.0
PARAM = "Device(dev) foo"


class FakeClient:
    """In-memory stand-in for a pydase client backed by a dict of values."""

    def __init__(self, values: dict[str, object]) -> None:
        self.values = values

    def get_value(self, *, access_path: str) -> object:
        return self.values[access_path]

    def update_value(self, *, access_path: str, new_value: object) -> None:
        self.values[access_path] = new_value


@pytest.fixture
def device() -> SimpleNamespace:
    return SimpleNamespace(
        name="dev",
        url="ws://localhost:8001",
        status=DeviceStatus.ENABLED,
        retry_attempts=3,
        retry_delay_seconds=0.0,
    )


@pytest.fixture
def worker(
    device: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> HardwareProcessingWorker:
    def get_device_by_name(*, name: str) -> SimpleNamespace:
        assert name == device.name
        return device

    monkeypatch.setattr(
        worker_module.DeviceRepository,
        "get_device_by_name",
        staticmethod(get_device_by_name),
    )
    # Avoid connecting to real hardware when the worker is constructed.
    monkeypatch.setattr(worker_module, "HardwareController", lambda: object())
    w = HardwareProcessingWorker(
        hardware_processing_queue=None,  # type: ignore[arg-type]
        post_processing_queue=None,  # type: ignore[arg-type]
        manager=None,  # type: ignore[arg-type]
    )
    w._pydase_clients = {"dev": FakeClient({"foo": PRE_SCAN_VALUE})}  # type: ignore[dict-item]
    return w


def test_restore_returns_device_to_pre_scan_value(
    worker: HardwareProcessingWorker,
) -> None:
    client = worker._pydase_clients["dev"]

    worker._set_pydase_service_values(scanned_params={PARAM: FIRST_SCAN_POINT}, job_id=1)
    worker._set_pydase_service_values(
        scanned_params={PARAM: SECOND_SCAN_POINT}, job_id=1
    )
    assert client.get_value(access_path="foo") == SECOND_SCAN_POINT

    worker._restore_device_values(job_id=1)

    # Restored to the value captured before the first scan write, not the last point.
    assert client.get_value(access_path="foo") == PRE_SCAN_VALUE
    # Snapshot is cleaned up after restore.
    assert 1 not in worker._original_device_values


def test_original_value_captured_only_once(worker: HardwareProcessingWorker) -> None:
    worker._set_pydase_service_values(scanned_params={PARAM: FIRST_SCAN_POINT}, job_id=1)
    worker._set_pydase_service_values(
        scanned_params={PARAM: SECOND_SCAN_POINT}, job_id=1
    )
    assert worker._original_device_values[1][PARAM] == PRE_SCAN_VALUE


def test_restore_without_capture_is_noop(worker: HardwareProcessingWorker) -> None:
    # No scan writes happened for this job (e.g. cancelled before any point ran).
    worker._restore_device_values(job_id=999)
    assert worker._pydase_clients["dev"].get_value(access_path="foo") == PRE_SCAN_VALUE


def test_non_device_params_are_ignored(worker: HardwareProcessingWorker) -> None:
    worker._set_pydase_service_values(scanned_params={"bare_param": 3.0}, job_id=2)
    assert worker._original_device_values.get(2, {}) == {}


def test_restore_is_lenient_when_device_disabled(
    worker: HardwareProcessingWorker, device: SimpleNamespace
) -> None:
    worker._set_pydase_service_values(scanned_params={PARAM: FIRST_SCAN_POINT}, job_id=1)

    # Device becomes disabled between scan and teardown.
    device.status = DeviceStatus.DISABLED

    # Must not raise, and must not write the disabled device.
    worker._restore_device_values(job_id=1)
    assert worker._pydase_clients["dev"].get_value(access_path="foo") == FIRST_SCAN_POINT
    assert 1 not in worker._original_device_values
