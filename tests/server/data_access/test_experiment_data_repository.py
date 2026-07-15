from pathlib import Path
from types import SimpleNamespace
from typing import Any

import h5py
import numpy as np
import pytest
from sqlalchemy.exc import NoResultFound

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
            experiment_id=-2,
            number_of_shots=3,
            repetitions=1,
            readout_metadata=READOUT_METADATA,
            local_parameter_timestamp=None,
            parameters=[mock_scan_parameter("x")],
        )
        for data_point in DATA_POINTS:
            experiment_data_repository.write_experiment_data_point(h5file, data_point)
        experiment_data_full = experiment_data_repository.load_experiment_data(
            h5file, include_hardware_instructions=True
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
            experiment_id=-2,
            number_of_shots=3,
            repetitions=1,
            readout_metadata=READOUT_METADATA,
            local_parameter_timestamp=None,
            parameters=[mock_scan_parameter("x")],
        )
        for data_point in DATA_POINTS:
            experiment_data_repository.write_experiment_data_point(h5file, data_point)
        experiment_data_minimal = experiment_data_repository.load_experiment_data(
            h5file
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
            h5file, include_hardware_instructions=True
        )
    assert experiment_data == expected_experiment_data


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
                h5file, data_point_index, "RFSoC", instructions
            )


def _get_hw_instructions(
    job_id: int | None = None, index: int | None = None
) -> str | None:
    return (
        experiment_data_repository.ExperimentDataRepository.get_hardware_instructions(
            device_id="RFSoC", job_id=job_id, index=index
        )
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

    # latest: newest file that has instructions
    assert _get_hw_instructions() == "seq-2a"
    # job scope: last entry of that job
    assert _get_hw_instructions(job_id=1) == "seq-1b"
    # data point scope: entry active at the given index
    assert _get_hw_instructions(job_id=1, index=0) == "seq-1a"
    assert _get_hw_instructions(job_id=1, index=4) == "seq-1a"
    assert _get_hw_instructions(job_id=1, index=5) == "seq-1b"
    assert _get_hw_instructions(job_id=1, index=99) == "seq-1b"
    # data points before the first stored entry have no instructions
    assert _get_hw_instructions(job_id=0, index=1) is None
    assert _get_hw_instructions(job_id=0, index=2) == "seq-0a"
    # unknown job, missing file, and empty directory behave gracefully
    assert _get_hw_instructions(job_id=unknown_job_id) is None
    assert _get_hw_instructions(job_id=39) is None
    monkeypatch.setattr(
        experiment_data_repository,
        "get_config",
        lambda: SimpleNamespace(data=SimpleNamespace(results_dir=str(tmp_path / "x"))),
    )
    assert _get_hw_instructions() is None


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

    assert _get_hw_instructions() is None

    # Within the window it is found again.
    for i in range(1, limit + 1):
        (tmp_path / f"job-{i:02d}.h5").unlink()
    assert _get_hw_instructions() == "seq-old"


def mock_scan_parameter(variable_id: str, *, realtime: bool = False) -> Any:
    """Wrapper returning an Any type."""
    return MockScanParameter(variable_id, realtime=realtime)
