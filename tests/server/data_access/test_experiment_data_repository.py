import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import h5py
import numpy as np
import pytest
from sqlalchemy.exc import NoResultFound

from icon.config import latest
from icon.server.data_access.experiment_data import (
    ExperimentData,
    ExperimentDataPoint,
    ExperimentDeviceData,
    ExperimentDeviceDataPoint,
    ParameterValue,
    PlotWindowMetadata,
    PlotWindows,
    ReadoutMetadata,
    Readouts,
    ReadoutSequences,
)
from icon.server.data_access.repositories import experiment_data_repository
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataRepository as Repo,
)
from icon.server.data_access.repositories.job_run_repository import ScheduledRun

DATA_POINTS = [
    ExperimentDataPoint(
        index=0,
        scan_params={"x": 42.0},
        timestamp="2026-03-24 16:46:09.638101",
        device_data=[
            ExperimentDeviceDataPoint(
                device_id="Der Gerät",
                readouts=Readouts(
                    result_channels={"raw_counts": 2.5},
                    vector_channels={},
                    shot_channels={"raw_counts": [1, 5, 10]},
                ),
                hardware_instructions="...",
            ),
            ExperimentDeviceDataPoint(
                device_id="Der andere Gerät",
                readouts=Readouts(
                    result_channels={"raw_counts": 3.5},
                    vector_channels={},
                    shot_channels={"raw_counts": [10, 5, 1]},
                ),
                hardware_instructions="***",
            ),
        ],
    ),
    ExperimentDataPoint(
        index=1,
        scan_params={"x": 42.0},
        timestamp="2026-03-24 16:46:10.638101",
        device_data=[
            ExperimentDeviceDataPoint(
                device_id="Der Gerät",
                readouts=Readouts(
                    result_channels={"raw_counts": 5.0},
                    vector_channels={},
                    shot_channels={"raw_counts": [5, 5, 5]},
                ),
                hardware_instructions="....",
            ),
        ],
    ),
]
PLOT_WINDOW = PlotWindowMetadata(
    name="raw_counts",
    index=0,
    type="readout",
    channel_names=["raw_counts"],
)

READOUT_METADATA = [
    (
        "Der Gerät",
        ReadoutMetadata(
            readout_channel_names=["raw_counts"],
            shot_channel_names=["raw_counts"],
            vector_channel_names=[],
            readout_channel_windows=[PLOT_WINDOW],
            shot_channel_windows=[],
            vector_channel_windows=[],
        ),
    ),
    (
        "Der andere Gerät",
        ReadoutMetadata(
            readout_channel_names=["raw_counts"],
            shot_channel_names=["raw_counts"],
            vector_channel_names=[],
            readout_channel_windows=[],
            shot_channel_windows=[],
            vector_channel_windows=[],
        ),
    ),
]


def create_expected_experiment_data(
    *, with_hardware_instructions: bool
) -> ExperimentData:
    return ExperimentData(
        device_data=[
            ExperimentDeviceData(
                device_id="Der Gerät",
                readouts=ReadoutSequences(
                    result_channels={"raw_counts": {0: 2.5, 1: 5.0}},
                    vector_channels={},
                    shot_channels={"raw_counts": {0: [1, 5, 10], 1: [5, 5, 5]}},
                ),
                hardware_instructions=[(0, "..."), (1, "....")]
                if with_hardware_instructions
                else [],
                plot_windows=PlotWindows(result_channels=[PLOT_WINDOW]),
            ),
            ExperimentDeviceData(
                device_id="Der andere Gerät",
                readouts=ReadoutSequences(
                    result_channels={"raw_counts": {0: 3.5}},
                    vector_channels={},
                    shot_channels={"raw_counts": {0: [10, 5, 1]}},
                ),
                hardware_instructions=[(0, "***")]
                if with_hardware_instructions
                else [],
                plot_windows=PlotWindows(),
            ),
        ],
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


def test_experiment_data_io_with_hardware_instructions() -> None:
    expected_experiment_data = create_expected_experiment_data(
        with_hardware_instructions=True
    )
    with h5py.File.in_memory() as h5file:
        experiment_data_repository.prepare_readout_metadata(
            h5file,
            job_id=-1,
            experiment_id="test.MockExperiment (MockExperiment)",
            number_of_shots=3,
            repetitions=1,
            readout_metadata=READOUT_METADATA,
            local_parameter_timestamp=None,
            parameters=[mock_scan_parameter("x")],
        )
        for data_point in DATA_POINTS:
            experiment_data_repository.write_experiment_data_point(h5file, data_point)
        experiment_data_full = experiment_data_repository.load_experiment_data(
            h5file, include_hardware_instructions=True, include_all_shots=True
        )
    assert experiment_data_full == expected_experiment_data


def test_experiment_data_io_without_hardware_instructions() -> None:
    expected_experiment_data = create_expected_experiment_data(
        with_hardware_instructions=False
    )
    with h5py.File.in_memory() as h5file:
        experiment_data_repository.prepare_readout_metadata(
            h5file,
            job_id=-1,
            experiment_id="-2",
            number_of_shots=3,
            repetitions=1,
            readout_metadata=READOUT_METADATA,
            local_parameter_timestamp=None,
            parameters=[mock_scan_parameter("x")],
        )
        for data_point in DATA_POINTS:
            experiment_data_repository.write_experiment_data_point(h5file, data_point)
        experiment_data_minimal = experiment_data_repository.load_experiment_data(
            h5file, include_all_shots=True
        )
    assert experiment_data_minimal == expected_experiment_data


def prepare_legacy_h5(h5file: h5py.File) -> None:
    scan_parameters = [
        [("2026-08-17T09:01:50.753761", 0.0)],
        [("2026-08-17T09:01:53.890311", 1.0)],
    ]

    number_of_shots = 3
    h5file.attrs["number_of_data_points"] = len(scan_parameters)
    h5file.attrs["number_of_shots"] = number_of_shots
    h5file.attrs["experiment_id"] = (
        "experiment_library.experiments.readout_raw_counts.ExampleReadoutRawCounts (Example Readout Raw Counts)"
    )
    h5file.attrs["job_id"] = 42
    h5file.attrs["repetitions"] = 1
    h5file.attrs["realtime_scan"] = False
    h5file.create_dataset(
        "hardware_instructions",
        maxshape=(None,),
        chunks=True,
        dtype=[
            ("index", np.int32),
            ("Sequence", h5py.string_dtype()),
        ],
        compression="gzip",
        compression_opts=9,
        data=[(0, '{"header":{"version":"fake"}}')],
    )
    parameters_group = h5file.require_group("parameters")
    for param_id, value, dtype in [
        (
            "namespace='experiment_library.experiments.example_base.ExampleExperiment.ExampleExperiment' parameter_group='default' param_type='ParameterTypes.INT' name='shots'",
            0,
            np.int64,
        ),
        (
            "namespace='experiment_library.experiments.example_parameters.ExampleParameters.Parameter Example' parameter_group='default' param_type='ParameterTypes.AMPLITUDE' name='pulse_amplitude'",
            100.0,
            np.float64,
        ),
    ]:
        parameters_group.create_dataset(
            param_id,
            shape=(1,),
            maxshape=(None,),
            dtype=[("timestamp", "S26"), ("value", dtype)],
            data=[("2026-08-17T09:01:41.877728", value)],
        )
    h5file.create_dataset(
        "scan_parameters",
        maxshape=(None, 1),
        chunks=True,
        dtype=[
            ("timestamp", "S26"),
            (
                "namespace='experiment_library.globals.global_parameters' parameter_group='global_detection' param_type='ParameterTypes.AMPLITUDE' name='detection_amplitude'",
                np.float64,
            ),
        ],
        compression="gzip",
        compression_opts=9,
        data=scan_parameters,
    )
    result_dataset = h5file.create_dataset(
        "result_channels",
        maxshape=(None,),
        chunks=True,
        dtype=np.dtype([("raw counts", np.float64)]),
        compression="gzip",
        compression_opts=9,
        data=[24.94, 25.06],
    )
    result_dataset.attrs["Plot window metadata"] = (
        '[{"name": "readout", "index": 0, "type": "readout", "channel_names": ["raw counts"]}]'
    )
    shot_group = h5file.require_group("shot_channels")
    shot_group.attrs["Plot window metadata"] = (
        '[{"name": "histogram", "index": 0, "type": "histogram", "channel_names": ["raw counts"]}]'
    )
    shot_group.create_dataset(
        "raw counts",
        maxshape=(None, number_of_shots),
        chunks=True,
        dtype=np.float64,
        compression="gzip",
        compression_opts=9,
        data=np.array([[31, 23, 24], [21, 26, 33]]),
    )
    vector_group = h5file.require_group("vector_channels")
    vector_group.attrs["Plot window metadata"] = "[]"


def test_legacy_experiment_data_loading() -> None:
    expected_experiment_data = ExperimentData(
        device_data=[
            ExperimentDeviceData(
                device_id="zedboard",
                readouts=ReadoutSequences(
                    result_channels={"raw counts": {0: 24.94, 1: 25.06}},
                    vector_channels={},
                    shot_channels={"raw counts": {0: [31, 23, 24], 1: [21, 26, 33]}},
                ),
                hardware_instructions=[(0, '{"header":{"version":"fake"}}')],
                plot_windows=PlotWindows(
                    result_channels=[
                        PlotWindowMetadata(
                            name="readout",
                            index=0,
                            type="readout",
                            channel_names=["raw counts"],
                        )
                    ],
                    shot_channels=[
                        PlotWindowMetadata(
                            name="histogram",
                            index=0,
                            type="histogram",
                            channel_names=["raw counts"],
                        )
                    ],
                ),
            )
        ],
        scan_parameters={
            "timestamp": {
                0: "2026-08-17T09:01:50.753761",
                1: "2026-08-17T09:01:53.890311",
            },
            "namespace='experiment_library.globals.global_parameters' parameter_group='global_detection' param_type='ParameterTypes.AMPLITUDE' name='detection_amplitude'": {
                0: 0.0,
                1: 1.0,
            },
        },
        realtime_scan=False,
        total_data_points=2,
        parameters={
            "namespace='experiment_library.experiments.example_base.ExampleExperiment.ExampleExperiment' parameter_group='default' param_type='ParameterTypes.INT' name='shots'": ParameterValue(
                timestamp="2026-08-17T09:01:41.877728", value=0
            ),
            "namespace='experiment_library.experiments.example_parameters.ExampleParameters.Parameter Example' parameter_group='default' param_type='ParameterTypes.AMPLITUDE' name='pulse_amplitude'": ParameterValue(
                timestamp="2026-08-17T09:01:41.877728", value=100.0
            ),
        },
    )
    with h5py.File.in_memory() as h5file:
        prepare_legacy_h5(h5file)
        experiment_data = experiment_data_repository.load_experiment_data(
            h5file, include_hardware_instructions=True, include_all_shots=True
        )
    assert experiment_data == expected_experiment_data


class MockScanParameter:
    """So we dont need the SQL ScanParameter type."""

    def __init__(self, variable_id: str, *, realtime: bool = False) -> None:
        self.variable_id = variable_id
        self.realtime = realtime
        self.device = None


def _write_instruction_file(path: Path, entries: list[tuple[int, str]]) -> None:
    path.parent.mkdir(exist_ok=True)
    with h5py.File(path, "w") as h5file:
        for data_point_index, instructions in entries:
            experiment_data_repository.write_hardware_instructions_to_dataset(
                h5file, data_point_index, "RFSoC", instructions
            )


UNKNOWN_JOB_ID = 42
"""Job without a run in the stubbed run table."""


def _scheduled_time(job_id: int) -> datetime:
    """Return the stubbed scheduled time of a job; jobs 1 and 2 straddle midnight."""
    # Naive, like the scheduled times read back from SQLite.
    return datetime(2026, 3, 24, 23, 58) + timedelta(minutes=job_id)  # noqa: DTZ001


_EXPERIMENT_ID = "experiment_library.experiments.ramsey.Ramsey (Ramsey fine)"


def _scheduled_run(job_id: int) -> ScheduledRun:
    return ScheduledRun(_scheduled_time(job_id), _EXPERIMENT_ID)


def _result_file(results_dir: Path, job_id: int) -> Path:
    """Return the result file of a job, in the day folder of its scheduled time."""
    scheduled_time = _scheduled_time(job_id)
    return (
        results_dir
        / f"{scheduled_time:%Y-%m-%d}"
        / f"{scheduled_time:%Y%m%dT%H%M%S.%f}_Ramsey_fine.h5"
    )


def _fake_job_runs(monkeypatch: pytest.MonkeyPatch, recent_job_ids: list[int]) -> None:
    """Stub the run table lookups; `recent_job_ids` lists the newest runs first."""

    def get_scheduled_run_by_job_id(*, job_id: int) -> ScheduledRun:
        if job_id == UNKNOWN_JOB_ID:
            raise NoResultFound
        return _scheduled_run(job_id)

    monkeypatch.setattr(
        experiment_data_repository.JobRunRepository,
        "get_scheduled_run_by_job_id",
        get_scheduled_run_by_job_id,
    )
    monkeypatch.setattr(
        experiment_data_repository.JobRunRepository,
        "get_recent_scheduled_runs",
        lambda *, limit: [_scheduled_run(i) for i in recent_job_ids[:limit]],
    )


@pytest.mark.parametrize(
    ("experiment_id", "filename"),
    [
        ("mod.Ramsey (Cool Det)", "20260324T235900.000000_Cool_Det.h5"),
        ("mod.Ramsey (Ramsey (2))", "20260324T235900.000000_Ramsey_2.h5"),
        ("mod.Ramsey (Ünïcödé: a/b\\c)", "20260324T235900.000000_Unicode_a_b_c.h5"),
        ("mod.Ramsey (???)", "20260324T235900.000000.h5"),
        ("unparsed-id", "20260324T235900.000000_unparsed-id.h5"),
        (f"mod.Ramsey ({'x' * 100})", f"20260324T235900.000000_{'x' * 64}.h5"),
    ],
)
def test_result_path_names_file_after_time_and_experiment(
    experiment_id: str, filename: str
) -> None:
    run = ScheduledRun(_scheduled_time(1), experiment_id)

    assert experiment_data_repository.result_path(Path("results"), run) == (
        Path("results") / "2026-03-24" / filename
    )


def test_result_path_keeps_time_zone() -> None:
    run = ScheduledRun(datetime(2026, 3, 24, 23, 59, tzinfo=UTC), "mod.Ramsey (A)")

    assert experiment_data_repository.result_path(Path("results"), run) == (
        Path("results") / "2026-03-24" / "20260324T235900.000000+0000_A.h5"
    )


def test_get_hardware_instructions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    # Two jobs; instructions are stored deduplicated: the entry index marks the
    # data point at which the instructions changed.
    _write_instruction_file(_result_file(tmp_path, 1), [(0, "seq-1a"), (5, "seq-1b")])
    _write_instruction_file(_result_file(tmp_path, 2), [(0, "seq-2a")])
    # Older than job-2 so that it does not affect the latest-file lookup.
    _write_instruction_file(_result_file(tmp_path, 0), [(2, "seq-0a")])
    # A newer file without instructions must be skipped for the latest scope.
    _write_instruction_file(_result_file(tmp_path, 3), [])
    _fake_job_runs(monkeypatch, [3, 2, 1, 0])

    # latest: newest file that has instructions
    assert Repo.get_hardware_instructions(device_id="RFSoC") == "seq-2a"
    # job scope: last entry of that job
    assert Repo.get_hardware_instructions(device_id="RFSoC", job_id=1) == "seq-1b"
    # data point scope: entry active at the given index
    assert (
        Repo.get_hardware_instructions(device_id="RFSoC", job_id=1, index=0) == "seq-1a"
    )
    assert (
        Repo.get_hardware_instructions(device_id="RFSoC", job_id=1, index=4) == "seq-1a"
    )
    assert (
        Repo.get_hardware_instructions(device_id="RFSoC", job_id=1, index=5) == "seq-1b"
    )
    assert (
        Repo.get_hardware_instructions(device_id="RFSoC", job_id=1, index=99)
        == "seq-1b"
    )
    # data points before the first stored entry have no instructions
    assert Repo.get_hardware_instructions(device_id="RFSoC", job_id=0, index=1) is None
    assert (
        Repo.get_hardware_instructions(device_id="RFSoC", job_id=0, index=2) == "seq-0a"
    )
    # unknown job, missing file, and empty directory behave gracefully
    assert (
        Repo.get_hardware_instructions(device_id="RFSoC", job_id=UNKNOWN_JOB_ID) is None
    )
    assert Repo.get_hardware_instructions(device_id="RFSoC", job_id=39) is None
    monkeypatch.setattr(
        experiment_data_repository,
        "get_config",
        lambda: SimpleNamespace(
            data=latest.DataConfiguration(results_dir=str(tmp_path / "x"))
        ),
    )
    assert Repo.get_hardware_instructions(device_id="RFSoC") is None


def test_get_hardware_instructions_only_searches_recent_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    limit = experiment_data_repository.MOST_RECENT_JOB_RUNS
    # Only the oldest run has instructions, and it is pushed out of the window
    # by newer runs whose files hold none.
    _write_instruction_file(_result_file(tmp_path, 0), [(0, "seq-old")])
    for i in range(1, limit + 1):
        _write_instruction_file(_result_file(tmp_path, i), [])
    newest_first = list(range(limit, -1, -1))
    _fake_job_runs(monkeypatch, newest_first)

    assert Repo.get_hardware_instructions(device_id="RFSoC") is None

    # Within the window it is found again.
    _fake_job_runs(monkeypatch, newest_first[1:])
    assert Repo.get_hardware_instructions(device_id="RFSoC") == "seq-old"


def test_get_hardware_instructions_skips_runs_without_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    # The newest run's file was archived or never written; the search continues.
    _write_instruction_file(_result_file(tmp_path, 1), [(0, "seq-1a")])
    _fake_job_runs(monkeypatch, [2, 1])

    assert Repo.get_hardware_instructions(device_id="RFSoC") == "seq-1a"


def test_initialize_for_job_id_creates_file_in_day_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    _fake_job_runs(monkeypatch, [])

    Repo.initialize_for_job_id(job_id=1)
    Repo.initialize_for_job_id(job_id=2)

    first = tmp_path / "2026-03-24" / "20260324T235900.000000_Ramsey_fine.h5"
    second = tmp_path / "2026-03-25" / "20260325T000000.000000_Ramsey_fine.h5"
    assert first.is_file()
    assert second.is_file()
    assert experiment_data_repository.get_result_path_by_job_id(1) == first
    assert experiment_data_repository.get_result_path_by_job_id(2) == second


def test_require_day_folder_layout_rejects_flat_result_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    _result_file(tmp_path, 1).parent.mkdir()
    _result_file(tmp_path, 1).touch()
    # Not named like a result file, so not ICON's to move.
    (tmp_path / "analysis.h5").touch()
    (tmp_path / "2026-03-24T23:59:00.h5").touch()

    experiment_data_repository.require_day_folder_layout(tmp_path)

    # Written before day folders were introduced.
    flat_file = tmp_path / f"{_scheduled_time(2)}.h5"
    flat_file.touch()

    assert experiment_data_repository.find_flat_result_files(tmp_path) == [
        (flat_file, _scheduled_time(2))
    ]
    with pytest.raises(
        experiment_data_repository.FlatResultLayoutError,
        match=re.escape(f"1 result file(s) sit directly in {str(tmp_path)!r}"),
    ):
        experiment_data_repository.require_day_folder_layout(tmp_path)


def test_initialize_for_job_id_requires_existing_results_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results_dir = tmp_path / "missing"
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(results_dir))
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    _fake_job_runs(monkeypatch, [])

    with pytest.raises(
        experiment_data_repository.ResultsDirectoryNotFoundError,
        match=re.escape(f"Results directory {str(results_dir)!r} does not exist"),
    ):
        Repo.initialize_for_job_id(job_id=1)
    assert not results_dir.exists()


def test_ensure_results_dir_creates_missing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results_dir = tmp_path / "results"
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(results_dir))
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    assert experiment_data_repository.ensure_results_dir() == results_dir
    assert results_dir.is_dir()
    # An existing directory is used as is.
    (results_dir / "kept.h5").touch()
    assert experiment_data_repository.ensure_results_dir() == results_dir
    assert (results_dir / "kept.h5").is_file()


def test_ensure_results_dir_does_not_create_parents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results_dir = tmp_path / "unmounted" / "results"
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(results_dir))
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    with pytest.raises(
        experiment_data_repository.ResultsDirectoryNotFoundError,
        match=re.escape(
            f"Results directory {str(results_dir)!r} cannot be created "
            "(No such file or directory)"
        ),
    ):
        experiment_data_repository.ensure_results_dir()
    assert not results_dir.parent.exists()


def test_ensure_results_dir_rejects_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results_dir = tmp_path / "results"
    results_dir.touch()
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(results_dir))
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    with pytest.raises(
        experiment_data_repository.ResultsDirectoryNotFoundError,
        match=re.escape(f"Results directory {str(results_dir)!r} is not a directory"),
    ):
        experiment_data_repository.ensure_results_dir()


def test_prepare_results_dir_stops_startup_on_flat_result_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    experiment_data_repository.prepare_results_dir()

    (tmp_path / f"{_scheduled_time(1)}.h5").touch()
    with pytest.raises(SystemExit) as exc_info:
        experiment_data_repository.prepare_results_dir()
    assert exc_info.value.code == 1


def test_prepare_results_dir_only_warns_about_unusable_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    results_dir = tmp_path / "unmounted" / "results"
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(results_dir))
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    experiment_data_repository.prepare_results_dir()

    assert "cannot be created" in caplog.text


def test_results_dir_expands_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir="~/results"))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    _fake_job_runs(monkeypatch, [])
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    assert experiment_data_repository.require_results_dir() == results_dir
    assert experiment_data_repository.get_result_path_by_job_id(1) == _result_file(
        results_dir, 1
    )


def test_require_results_dir_rejects_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results_dir = tmp_path / "results"
    results_dir.touch()
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(results_dir))
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    with pytest.raises(
        experiment_data_repository.ResultsDirectoryNotFoundError,
        match=re.escape(f"Results directory {str(results_dir)!r} is not a directory"),
    ):
        experiment_data_repository.require_results_dir()


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission checks")
def test_require_results_dir_reports_permission_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked = tmp_path / "locked"
    results_dir = locked / "results"
    results_dir.mkdir(parents=True)
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(results_dir))
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    locked.chmod(0)
    try:
        with pytest.raises(
            experiment_data_repository.ResultsDirectoryNotFoundError,
            match=re.escape(
                f"Results directory {str(results_dir)!r} cannot be accessed "
                "(Permission denied)"
            ),
        ):
            experiment_data_repository.require_results_dir()
    finally:
        locked.chmod(0o755)


def test_require_results_dir_reports_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir="missing"))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    with pytest.raises(
        experiment_data_repository.ResultsDirectoryNotFoundError,
        match=re.escape(
            f"Results directory {str(tmp_path / 'missing')!r} does not exist"
        ),
    ):
        experiment_data_repository.require_results_dir()


def mock_scan_parameter(variable_id: str, *, realtime: bool = False) -> Any:
    """Wrapper returning an Any type."""
    return MockScanParameter(variable_id, realtime=realtime)
