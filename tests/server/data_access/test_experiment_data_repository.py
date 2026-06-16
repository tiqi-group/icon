import h5py

from icon.server.data_access.experiment_data import (
    ExperimentData,
    ExperimentDataPoint,
    ExperimentDeviceData,
    ExperimentDeviceDataPoint,
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
            device_data=[
                ExperimentDeviceDataPoint(
                    device_id="Der Gerät",
                    readouts=Readouts(
                        result_channels={"raw_counts": 2.5},
                        vector_channels={},
                        shot_channels={"raw_counts": [1, 5, 10]},
                    ),
                    hardware_instructions=b"...",
                ),
                ExperimentDeviceDataPoint(
                    device_id="Der andere Gerät",
                    readouts=Readouts(
                        result_channels={"raw_counts": 3.5},
                        vector_channels={},
                        shot_channels={"raw_counts": [10, 5, 1]},
                    ),
                    hardware_instructions=b"***",
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
                    hardware_instructions=b"....",
                ),
            ],
        ),
    ]
    plot_window = PlotWindowMetadata(
        name="raw_counts",
        index=0,
        type="readout",
        channel_names=["raw_counts"],
    )
    expected_experiment_data = ExperimentData(
        device_data=[
            ExperimentDeviceData(
                device_id="Der Gerät",
                readouts=ReadoutSequences(
                    result_channels={"raw_counts": {0: 2.5, 1: 5.0}},
                    vector_channels={},
                    shot_channels={"raw_counts": {0: [1, 5, 10], 1: [5, 5, 5]}},
                ),
                hardware_instructions=[(0, b"..."), (1, b"....")],
                plot_windows=PlotWindows(result_channels=[plot_window]),
            ),
            ExperimentDeviceData(
                device_id="Der andere Gerät",
                readouts=ReadoutSequences(
                    result_channels={"raw_counts": {0: 3.5}},
                    vector_channels={},
                    shot_channels={"raw_counts": {0: [10, 5, 1]}},
                ),
                hardware_instructions=[(0, b"***")],
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
    with h5py.File.in_memory() as h5file:
        experiment_data_repository.prepare_readout_metadata(
            h5file,
            job_id=-1,
            experiment_id=-2,
            number_of_shots=3,
            repetitions=1,
            readout_metadata=[
                (
                    "Der Gerät",
                    ReadoutMetadata(
                        readout_channel_names=["raw_counts"],
                        shot_channel_names=["raw_counts"],
                        vector_channel_names=[],
                        readout_channel_windows=[plot_window],
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
            ],
            local_parameter_timestamp=None,
            parameters=[MockScanParameter("x")],
        )
        for data_point in data_points:
            experiment_data_repository.write_experiment_data_point(h5file, data_point)
        experiment_data = experiment_data_repository.load_experiment_data(h5file)
    assert experiment_data == expected_experiment_data


class MockScanParameter:
    """So we dont need the SQL ScanParameter type."""

    def __init__(self, variable_id: str, *, realtime: bool = False) -> None:
        self.variable_id = variable_id
        self.realtime = realtime
        self.device = None
