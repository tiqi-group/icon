import dataclasses
import threading
import time
from pathlib import Path
from typing import Any

import h5py
import pytest
from filelock import FileLock

from icon.server.data_access.experiment_data import (
    ExperimentData,
    ExperimentDataPoint,
    PlotWindowMetadata,
    PlotWindows,
    ReadoutMetadata,
    Readouts,
    ReadoutSequences,
)
from icon.server.data_access.repositories import experiment_data_repository


def test_experiment_data_io() -> None:
    data_points = [
        ExperimentDataPoint(
            index=0,
            scan_params={"x": 42.0},
            timestamp="2026-03-24 16:46:09.638101",
            readouts=Readouts(
                result_channels={"raw_counts": 2.5},
                vector_channels={},
                shot_channels={"raw_counts": [1, 5, 10]},
            ),
            hardware_instructions="...",
        ),
        ExperimentDataPoint(
            index=1,
            scan_params={"x": 42.0},
            timestamp="2026-03-24 16:46:10.638101",
            readouts=Readouts(
                result_channels={"raw_counts": 5.0},
                vector_channels={},
                shot_channels={"raw_counts": [5, 5, 5]},
            ),
            hardware_instructions="....",
        ),
    ]
    plot_window = PlotWindowMetadata(
        name="raw_counts",
        index=0,
        type="readout",
        channel_names=["raw_counts"],
    )
    expected_experiment_data = ExperimentData(
        readouts=ReadoutSequences(
            result_channels={"raw_counts": {0: 2.5, 1: 5.0}},
            vector_channels={},
            shot_channels={"raw_counts": {0: [1, 5, 10], 1: [5, 5, 5]}},
        ),
        hardware_instructions=[(0, "..."), (1, "....")],
        plot_windows=PlotWindows(result_channels=[plot_window]),
        scan_parameters={
            "timestamp": {
                0: "2026-03-24 16:46:09.638101",
                1: "2026-03-24 16:46:10.638101",
            },
            "x": {0: 42.0, 1: 42.0},
        },
        realtime_scan=False,
        total_data_points=2,
    )
    with h5py.File.in_memory() as h5file:
        param: Any = MockScanParameter("x")
        experiment_data_repository.prepare_readout_metadata(
            h5file,
            job_id=-1,
            experiment_id=-2,
            number_of_shots=3,
            repetitions=1,
            readout_metadata=ReadoutMetadata(
                readout_channel_names=["raw_counts"],
                shot_channel_names=["raw_counts"],
                vector_channel_names=[],
                readout_channel_windows=[plot_window],
                shot_channel_windows=[],
                vector_channel_windows=[],
            ),
            local_parameter_timestamp=None,
            parameters=[param],
        )
        for data_point in data_points:
            experiment_data_repository.write_experiment_data_point(h5file, data_point)
        experiment_data_minimal = experiment_data_repository.load_experiment_data(
            h5file
        )
        experiment_data_full = experiment_data_repository.load_experiment_data(
            h5file, include_hardware_instructions=True
        )
    assert experiment_data_minimal == dataclasses.replace(
        expected_experiment_data, hardware_instructions=[]
    )
    assert experiment_data_full == expected_experiment_data


class MockScanParameter:
    """So we dont need the SQL ScanParameter type."""

    def __init__(self, variable_id: str, *, realtime: bool = False) -> None:
        self.variable_id = variable_id
        self.realtime = realtime
        self.device = None


def test_h5_open_waits_for_writer(tmp_path: Path) -> None:
    path = tmp_path / "job.h5"
    with h5py.File(path, "w"):
        pass

    writer_done = threading.Event()
    reader_done = threading.Event()
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            with experiment_data_repository.h5_open(path, "a") as h5file:
                h5file.attrs["marker"] = 1
                time.sleep(0.3)
        except BaseException as exc:
            errors.append(exc)
        finally:
            writer_done.set()

    def reader() -> None:
        try:
            time.sleep(0.05)
            with experiment_data_repository.h5_open(path, "r") as h5file:
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
        experiment_data_repository.h5_open(path, "r"),
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

    monkeypatch.setattr(experiment_data_repository.h5py, "File", counting_file)
    with (
        pytest.raises(OSError, match="disk full"),
        experiment_data_repository.h5_open(path, "a"),
    ):
        raise OSError("disk full")
    assert opens == 1


def test_h5_open_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "job.h5"
    monkeypatch.setattr(experiment_data_repository, "OPEN_TIMEOUT", 0.2)

    held = threading.Event()
    stop = threading.Event()

    def holder() -> None:
        lock = FileLock(experiment_data_repository._h5_lock_path(path))
        with lock:
            held.set()
            stop.wait(timeout=5)

    thread = threading.Thread(target=holder, daemon=True)
    thread.start()
    assert held.wait(timeout=2)
    try:
        with (
            pytest.raises(TimeoutError, match="Timed out opening HDF5 file"),
            experiment_data_repository.h5_open(path, "a"),
        ):
            pass
    finally:
        stop.set()
        thread.join(timeout=2)
