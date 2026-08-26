import json
import logging
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import h5py
import pytest
from filelock import FileLock
from sqlalchemy.exc import NoResultFound

from icon.server.data_access.repositories import experiment_data_repository as edr


@pytest.fixture
def results_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ExperimentDataRepository at a temporary results directory."""
    fake_config = SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path)))
    monkeypatch.setattr(edr, "get_config", lambda: fake_config)
    return tmp_path


@pytest.fixture
def job_filename(monkeypatch: pytest.MonkeyPatch) -> str:
    """Bypass the DB-backed filename lookup used by write_experiment_data_by_job_id."""
    filename = "test_job.h5"
    monkeypatch.setattr(edr, "get_filename_by_job_id", lambda job_id: filename)  # noqa: ARG005
    return filename


def test_write_shot_channels_to_datasets_writes_correctly_sized_channels(
    tmp_path: Path,
) -> None:
    h5_path = tmp_path / "test.h5"

    with edr.h5_open(h5_path, "a") as h5file:
        edr.write_shot_channels_to_datasets(
            h5file=h5file,
            data_point_index=0,
            shot_channels={"raw_counts": [1, 2, 3]},
            number_of_data_points=0,
            number_of_shots=3,
            job_id=1,
        )

    with edr.h5_open(h5_path, "r") as h5file:
        assert list(h5file["shot_channels"]["raw_counts"][0]) == [1.0, 2.0, 3.0]


def test_write_shot_channels_to_datasets_skips_mismatched_channel(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A mismatched shot channel is logged and skipped.

    It must not raise and must not affect other, correctly-sized channels.
    """
    h5_path = tmp_path / "test.h5"

    with caplog.at_level(logging.ERROR), edr.h5_open(h5_path, "a") as h5file:
        edr.write_shot_channels_to_datasets(
            h5file=h5file,
            data_point_index=0,
            shot_channels={"raw_counts": [1, 2, 3], "repeated_shots": []},
            number_of_data_points=0,
            number_of_shots=3,
            job_id=42,
        )

    with edr.h5_open(h5_path, "r") as h5file:
        shot_group = h5file["shot_channels"]
        assert list(shot_group["raw_counts"][0]) == [1.0, 2.0, 3.0]
        assert "repeated_shots" not in shot_group

    assert any(
        record.levelno == logging.ERROR
        and "repeated_shots" in record.getMessage()
        and "42" in record.getMessage()
        for record in caplog.records
    )


def test_write_experiment_data_by_job_id_skips_mismatched_shot_channel(
    results_dir: Path, job_filename: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The end-to-end write path must not crash on a mismatched shot channel.

    E.g. an unwired 'repeated_shots' channel, and must still persist everything
    else correctly.
    """
    h5_path = results_dir / job_filename
    with edr.h5_open(h5_path, "a") as h5file:
        h5file.attrs["number_of_shots"] = 3
        h5file.attrs["number_of_data_points"] = 0

    data_point = edr.ExperimentDataPoint(
        result_channels={"raw_counts": 2.0},
        vector_channels={},
        shot_channels={"raw_counts": [1, 2, 3], "repeated_shots": []},
        index=0,
        scan_params={"x": 1.0},
        timestamp="2026-07-01T00:00:00",
        sequence_json="{}",
    )

    with caplog.at_level(logging.ERROR):
        edr.ExperimentDataRepository.write_experiment_data_by_job_id(
            job_id=1, data_point=data_point
        )

    with edr.h5_open(h5_path, "r") as h5file:
        assert h5file.attrs["number_of_data_points"] == 1
        shot_group = h5file["shot_channels"]
        assert list(shot_group["raw_counts"][0]) == [1.0, 2.0, 3.0]
        assert "repeated_shots" not in shot_group

    assert any(
        record.levelno == logging.ERROR and "repeated_shots" in record.getMessage()
        for record in caplog.records
    )


def _leaf(type_: str, value: object) -> dict:
    """Build a minimal pydase SerializedObject leaf node for tests."""
    return {
        "full_access_path": "",
        "doc": None,
        "readonly": False,
        "type": type_,
        "value": value,
    }


def _container(type_: str, value: dict, **extra: object) -> dict:
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


def _write_instruction_file(path: Path, entries: list[tuple[int, str]]) -> None:
    with edr.h5_open(path, "w") as h5file:
        for data_point_index, instructions in entries:
            edr.write_sequence_json_to_dataset(h5file, data_point_index, instructions)


def test_get_hardware_instructions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path)))
    monkeypatch.setattr(edr, "get_config", lambda: config)
    unknown_job_id = 42

    def filename(job_id: int) -> str:
        if job_id == unknown_job_id:
            raise NoResultFound
        return f"job-{job_id}.h5"

    monkeypatch.setattr(edr, "get_filename_by_job_id", filename)

    _write_instruction_file(tmp_path / "job-1.h5", [(0, "seq-1a"), (5, "seq-1b")])
    _write_instruction_file(tmp_path / "job-2.h5", [(0, "seq-2a")])
    _write_instruction_file(tmp_path / "job-0.h5", [(2, "seq-0a")])
    with edr.h5_open(tmp_path / "job-3.h5", "w"):
        pass  # newer file without instructions must be skipped for latest scope

    get = edr.ExperimentDataRepository.get_hardware_instructions
    # latest scope: newest file that actually has instructions
    assert get() == "seq-2a"
    # job scope: last entry of that job
    assert get(job_id=1) == "seq-1b"
    # data point scope: the entry active at the given index
    assert get(job_id=1, index=0) == "seq-1a"
    assert get(job_id=1, index=4) == "seq-1a"
    assert get(job_id=1, index=5) == "seq-1b"
    assert get(job_id=1, index=99) == "seq-1b"
    # data points before the first stored entry have no instructions
    assert get(job_id=0, index=1) is None
    assert get(job_id=0, index=2) == "seq-0a"
    # unknown job, missing file, and empty results dir behave gracefully
    assert get(job_id=unknown_job_id) is None
    assert get(job_id=39) is None
    monkeypatch.setattr(
        edr,
        "get_config",
        lambda: SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path / "x"))),
    )
    assert get() is None


def test_h5_open_waits_for_writer(tmp_path: Path) -> None:
    path = tmp_path / "job.h5"
    with h5py.File(path, "w"):
        pass

    writer_done = threading.Event()
    reader_done = threading.Event()
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            with edr.h5_open(path, "a") as h5file:
                h5file.attrs["marker"] = 1
                time.sleep(0.3)
        except BaseException as exc:
            errors.append(exc)
        finally:
            writer_done.set()

    def reader() -> None:
        try:
            time.sleep(0.05)
            with edr.h5_open(path, "r") as h5file:
                assert h5file.attrs["marker"] == 1
        except BaseException as exc:
            errors.append(exc)
        finally:
            reader_done.set()

    threading.Thread(target=writer, daemon=True).start()
    threading.Thread(target=reader, daemon=True).start()
    assert reader_done.wait(timeout=5)
    assert writer_done.wait(timeout=5)
    assert errors == []


def test_h5_open_missing_file_raises_immediately(tmp_path: Path) -> None:
    path = tmp_path / "missing.h5"
    start = time.monotonic()
    with (
        pytest.raises(FileNotFoundError),
        edr.h5_open(path, "r"),
    ):
        pass
    assert time.monotonic() - start < 1.0


def test_h5_open_does_not_retry_body_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "job.h5"
    with h5py.File(path, "w"):
        pass

    opens = 0
    original = h5py.File

    def counting_file(*args: Any, **kwargs: Any) -> Any:
        nonlocal opens
        opens += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(edr.h5py, "File", counting_file)
    with (
        pytest.raises(OSError, match="disk full"),
        edr.h5_open(path, "a"),
    ):
        raise OSError("disk full")
    assert opens == 1


def test_h5_open_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "job.h5"
    monkeypatch.setattr(edr, "OPEN_TIMEOUT", 0.2)

    held = threading.Event()
    stop = threading.Event()

    def holder() -> None:
        lock = FileLock(edr._h5_lock_path(path))
        with lock:
            held.set()
            stop.wait(timeout=5)

    thread = threading.Thread(target=holder, daemon=True)
    thread.start()
    assert held.wait(timeout=2)
    try:
        with (
            pytest.raises(TimeoutError, match="Timed out opening HDF5 file"),
            edr.h5_open(path, "a"),
        ):
            pass
    finally:
        stop.set()
        thread.join(timeout=2)
