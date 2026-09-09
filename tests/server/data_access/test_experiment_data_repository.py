import dataclasses
from datetime import UTC, datetime
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

    def resolve(job_id: int) -> Path:
        if job_id == unknown_job_id:
            raise NoResultFound
        return tmp_path / f"job-{job_id}.h5"

    monkeypatch.setattr(
        experiment_data_repository, "resolve_h5_path_by_job_id", resolve
    )

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


def test_get_hardware_instructions_only_searches_recent_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    limit = experiment_data_repository.MOST_RECENT_RESULT_FILES
    # Only the oldest file has instructions, and it is pushed out of the window
    # by newer files without any.
    _write_instruction_file(tmp_path / "job-00.h5", [(0, "seq-old")])
    for i in range(1, limit + 1):
        with h5py.File(tmp_path / f"job-{i:02d}.h5", "w"):
            pass

    get = experiment_data_repository.ExperimentDataRepository.get_hardware_instructions
    assert get() is None

    # Within the window it is found again.
    for i in range(1, limit + 1):
        (tmp_path / f"job-{i:02d}.h5").unlink()
    assert get() == "seq-old"


def test_format_h5_filename_includes_job_id() -> None:
    scheduled = datetime(2026, 8, 11, 13, 41, 0, 123456, tzinfo=UTC)
    name = experiment_data_repository.format_h5_filename(scheduled, 42)
    assert name == "2026-08-11T13-41-00.123456+0000_job42.h5"
    assert ":" not in name


def test_h5_date_subdir_is_year_month_day() -> None:
    scheduled = datetime(2026, 8, 11, 13, 41, 0, tzinfo=UTC)
    assert experiment_data_repository.h5_date_subdir(scheduled) == Path("2026/08/11")


def test_resolve_h5_path_uses_dated_layout_for_new_files(tmp_path: Path) -> None:
    scheduled = datetime(2026, 8, 11, 13, 41, 0, 123456, tzinfo=UTC)
    path = experiment_data_repository.resolve_h5_path(
        scheduled, 7, results_dir=tmp_path
    )
    assert path == tmp_path / "2026" / "08" / "11" / (
        "2026-08-11T13-41-00.123456+0000_job7.h5"
    )


def test_get_hardware_instructions_searches_dated_subdirectories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    nested = tmp_path / "2026" / "09" / "04"
    nested.mkdir(parents=True)
    _write_instruction_file(nested / "run.h5", [(0, "seq-nested")])

    get = experiment_data_repository.ExperimentDataRepository.get_hardware_instructions
    assert get() == "seq-nested"


def test_resolve_h5_path_falls_back_to_flat_safe_name(tmp_path: Path) -> None:
    scheduled = datetime(2026, 8, 11, 13, 41, 0, 123456, tzinfo=UTC)
    safe_root = tmp_path / "2026-08-11T13-41-00.123456+0000.h5"
    safe_root.write_bytes(b"x")
    assert (
        experiment_data_repository.resolve_h5_path(scheduled, 7, results_dir=tmp_path)
        == safe_root
    )
