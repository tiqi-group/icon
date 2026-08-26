import dataclasses
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import h5py
import pytest
from sqlalchemy.exc import NoResultFound

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


def _write_instruction_file(path: Path, entries: list[tuple[int, str]]) -> None:
    with h5py.File(path, "w") as h5file:
        for data_point_index, instructions in entries:
            experiment_data_repository.write_hardware_instructions_to_dataset(
                h5file, data_point_index, instructions
            )


def test_get_hardware_instructions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    unknown_job_id = 42

    def filename(job_id: int) -> str:
        if job_id == unknown_job_id:
            raise NoResultFound
        return f"job-{job_id}.h5"

    monkeypatch.setattr(experiment_data_repository, "get_filename_by_job_id", filename)

    # Two jobs; instructions are stored deduplicated: the entry index marks the
    # data point at which the instructions changed.
    _write_instruction_file(tmp_path / "job-1.h5", [(0, "seq-1a"), (5, "seq-1b")])
    _write_instruction_file(tmp_path / "job-2.h5", [(0, "seq-2a")])
    # Sorts below job-2 so that it does not affect the latest-file lookup.
    _write_instruction_file(tmp_path / "job-0.h5", [(2, "seq-0a")])
    # A newer file without instructions must be skipped for the latest scope.
    with h5py.File(tmp_path / "job-3.h5", "w"):
        pass

    get = experiment_data_repository.ExperimentDataRepository.get_hardware_instructions
    # latest: newest file that has instructions
    assert get() == "seq-2a"
    # job scope: last entry of that job
    assert get(job_id=1) == "seq-1b"
    # data point scope: entry active at the given index
    assert get(job_id=1, index=0) == "seq-1a"
    assert get(job_id=1, index=4) == "seq-1a"
    assert get(job_id=1, index=5) == "seq-1b"
    assert get(job_id=1, index=99) == "seq-1b"
    # data points before the first stored entry have no instructions
    assert get(job_id=0, index=1) is None
    assert get(job_id=0, index=2) == "seq-0a"
    # unknown job, missing file, and empty directory behave gracefully
    assert get(job_id=unknown_job_id) is None
    assert get(job_id=39) is None
    monkeypatch.setattr(
        experiment_data_repository,
        "get_config",
        lambda: SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path / "x"))),
    )
    assert get() is None


def test_get_hardware_instructions_skips_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    monkeypatch.setattr(
        experiment_data_repository,
        "get_filename_by_job_id",
        lambda job_id: "job-9.h5",  # noqa: ARG005
    )

    _write_instruction_file(tmp_path / "job-1.h5", [(0, "seq-1a")])
    _write_instruction_file(tmp_path / "job-9.h5", [(0, "seq-9a")])

    original = experiment_data_repository._read_hardware_instructions

    def failing_read(path: Path, *, index: int | None) -> str | None:
        if path.name == "job-9.h5":
            raise OSError("unreadable file")
        return original(path, index=index)

    monkeypatch.setattr(
        experiment_data_repository, "_read_hardware_instructions", failing_read
    )

    get = experiment_data_repository.ExperimentDataRepository.get_hardware_instructions
    # Latest scope skips the unreadable newest file instead of failing.
    assert get() == "seq-1a"
    # Job scope degrades to None instead of raising.
    assert get(job_id=9) is None


def test_get_hardware_instructions_latest_scan_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    monkeypatch.setattr(experiment_data_repository, "_LATEST_SEQUENCE_SCAN_LIMIT", 3)

    # A file with instructions, hidden behind more sequence-less files than
    # the scan limit allows.
    _write_instruction_file(tmp_path / "job-0.h5", [(0, "seq-0a")])
    for i in range(1, 5):
        with experiment_data_repository.h5_open(tmp_path / f"job-{i}.h5", "w"):
            pass

    get = experiment_data_repository.ExperimentDataRepository.get_hardware_instructions
    assert get() is None

    # Within the limit it is found.
    monkeypatch.setattr(experiment_data_repository, "_LATEST_SEQUENCE_SCAN_LIMIT", 5)
    assert get() == "seq-0a"
