import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from icon.config import latest
from icon.server.data_access.repositories import experiment_data_repository as edr


@pytest.fixture
def results_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ExperimentDataRepository at a temporary results directory."""
    fake_config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(tmp_path))
    )
    monkeypatch.setattr(edr, "get_config", lambda: fake_config)
    return tmp_path


@pytest.fixture
def job_filename(monkeypatch: pytest.MonkeyPatch) -> str:
    """Bypass the DB-backed filename lookup used by write_experiment_data_by_job_id."""
    filename = "test_job.h5"
    monkeypatch.setattr(edr, "get_filename_by_job_id", lambda job_id: filename)  # noqa: ARG005
    return filename


def _leaf(type_: str, value: object) -> dict[str, Any]:
    """Build a minimal pydase SerializedObject leaf node for tests."""
    return {
        "full_access_path": "",
        "doc": None,
        "readonly": False,
        "type": type_,
        "value": value,
    }


def _container(type_: str, value: dict[str, Any], **extra: object) -> dict[str, Any]:
    """Build a minimal pydase SerializedObject container node for tests."""
    return {
        "full_access_path": "",
        "doc": None,
        "readonly": False,
        "type": type_,
        "value": value,
        **extra,
    }


def test_write_device_snapshots_by_job_id(results_dir: Path, job_filename: str) -> None:
    """Device snapshots are mirrored field-by-field; failed fetches keep an error attr."""
    voltage = 1.25
    gain = 10
    channels = [1.1, 2.2, 3.3]
    is_enabled = True

    dac_state = _container(
        "DataService",
        {
            "voltage": _leaf("float", voltage),
            "enabled": _leaf("bool", is_enabled),
            "status": {
                **_leaf("Enum", "RUNNING"),
                "name": "Status",
                "enum": {"IDLE": "idle", "RUNNING": "running"},
            },
            "setpoint": _leaf("Quantity", {"magnitude": 3.3, "unit": "V"}),
            "calibrate": {
                "full_access_path": "calibrate",
                "doc": None,
                "readonly": True,
                "type": "method",
                "value": None,
            },
            "sub": _container(
                "DataService",
                {
                    "gain": _leaf("int", gain),
                    "channels": _leaf("list", [_leaf("float", c) for c in channels]),
                },
            ),
        },
    )

    edr.ExperimentDataRepository.write_device_snapshots_by_job_id(
        job_id=1,
        snapshots=[
            edr.DeviceSnapshot(
                name="dac",
                url="ws://localhost:8001",
                timestamp="2026-07-17T10:00:00",
                state=dac_state,
            ),
            edr.DeviceSnapshot(
                name="down_device",
                url="ws://localhost:9999",
                timestamp="2026-07-17T10:00:00",
                state=None,
                error="not connected",
            ),
        ],
    )

    with edr.h5_open(results_dir / job_filename, "r") as h5file:
        params = h5file["devices"]["dac"]["parameters"]
        assert params.attrs["voltage"] == voltage
        assert params.attrs["enabled"]
        assert params.attrs["status"] == "RUNNING"
        assert params.attrs["setpoint"] == "3.3 V"
        assert "calibrate" not in params  # methods are actions, not state
        assert params["sub"].attrs["gain"] == gain
        assert list(params["sub"].attrs["channels"]) == channels

        down_device = h5file["devices"]["down_device"]
        assert down_device.attrs["error"] == "not connected"
        assert "parameters" not in down_device

    # A repeated snapshot for the same device replaces its state, dropping fields
    # that no longer exist (e.g. "sub" was removed).
    updated_voltage = 2.5
    edr.ExperimentDataRepository.write_device_snapshots_by_job_id(
        job_id=1,
        snapshots=[
            edr.DeviceSnapshot(
                name="dac",
                url="ws://localhost:8001",
                timestamp="2026-07-17T10:05:00",
                state=_container(
                    "DataService", {"voltage": _leaf("float", updated_voltage)}
                ),
            ),
        ],
    )

    with edr.h5_open(results_dir / job_filename, "r") as h5file:
        dac = h5file["devices"]["dac"]
        assert dac.attrs["timestamp"] == "2026-07-17T10:05:00"
        assert dac["parameters"].attrs["voltage"] == updated_voltage
        assert "sub" not in dac["parameters"]


def test_write_device_snapshots_by_job_id_expands_json_string_field(
    results_dir: Path, job_filename: str
) -> None:
    """A JSON-encoded string field gets expanded, not left as opaque text.

    Some device plugins report composite state that way.
    """
    gain = 10
    config_json = json.dumps({"gain": gain, "nested": {"offset": 0.5}})
    state = _container(
        "DataService",
        {
            "name": _leaf("str", "my_dac"),
            "not_json": _leaf("str", "[not actually json"),
            "config": _leaf("str", config_json),
        },
    )

    edr.ExperimentDataRepository.write_device_snapshots_by_job_id(
        job_id=1,
        snapshots=[
            edr.DeviceSnapshot(
                name="dac",
                url="ws://localhost:8001",
                timestamp="2026-07-17T10:00:00",
                state=state,
            ),
        ],
    )

    with edr.h5_open(results_dir / job_filename, "r") as h5file:
        params = h5file["devices"]["dac"]["parameters"]
        assert params.attrs["name"] == "my_dac"
        assert params.attrs["not_json"] == "[not actually json"
        assert params["config"].attrs["gain"] == gain
        assert params["config"]["nested"].attrs["offset"] == 0.5  # noqa: PLR2004
