from pathlib import Path

import h5py  # type: ignore
import numpy as np

from icon.server.data_access.repositories.experiment_data_repository import (
    _move_last_n_data_points_to_invalid,
    write_results_to_dataset,
    write_scan_parameters_and_timestamp_to_dataset,
    write_shot_channels_to_datasets,
    write_vector_channels_to_datasets,
)

NUMBER_OF_SHOTS = 4


def _write_data_points(h5file: h5py.File, count: int) -> None:
    """Populate an HDF5 file with ``count`` simple data points (indices 0..count-1)."""
    for index in range(count):
        # `number_of_data_points` is the running total *before* this write.
        write_scan_parameters_and_timestamp_to_dataset(
            h5file=h5file,
            data_point_index=index,
            scan_params={"freq": float(index)},
            timestamp=f"2024-01-01T00:00:{index:02d}.000000",
            number_of_data_points=index,
        )
        write_results_to_dataset(
            h5file=h5file,
            data_point_index=index,
            result_channels={"counts": float(index * 10)},
            number_of_data_points=index,
        )
        write_shot_channels_to_datasets(
            h5file=h5file,
            data_point_index=index,
            shot_channels={"shots": [index] * NUMBER_OF_SHOTS},
            number_of_data_points=index,
            number_of_shots=NUMBER_OF_SHOTS,
        )
        write_vector_channels_to_datasets(
            h5file=h5file,
            data_point_index=index,
            vector_channels={"trace": [float(index), float(index + 1)]},
        )
    h5file.attrs["number_of_shots"] = NUMBER_OF_SHOTS
    h5file.attrs["number_of_data_points"] = count


def test_move_last_n_data_points_to_invalid(tmp_path: Path) -> None:
    with h5py.File(tmp_path / "results.h5", "w") as h5file:
        _write_data_points(h5file, count=5)

        moved = _move_last_n_data_points_to_invalid(h5file, no_data_points=2)

        assert moved == [3, 4]
        assert h5file.attrs["number_of_data_points"] == 3

        # Live datasets shrink by the number of moved points.
        assert h5file["scan_parameters"].shape == (3, 1)
        assert h5file["result_channels"].shape == (3,)
        assert h5file["shot_channels/shots"].shape == (3, NUMBER_OF_SHOTS)
        assert set(h5file["vector_channels/trace"].keys()) == {"0", "1", "2"}

        # Invalid datasets hold the moved rows, tagged with their original index.
        assert h5file["invalid_indices"][:].tolist() == [3, 4]
        assert h5file["invalid_scan_parameters"]["freq"].flatten().tolist() == [
            3.0,
            4.0,
        ]
        assert h5file["invalid_result_channels"]["counts"].tolist() == [30.0, 40.0]
        np.testing.assert_array_equal(
            h5file["invalid_shot_channels/shots"][:],
            np.array([[3] * NUMBER_OF_SHOTS, [4] * NUMBER_OF_SHOTS], dtype=np.float64),
        )
        # Vector datasets are renamed to their append position (aligned to indices).
        assert set(h5file["invalid_vector_channels/trace"].keys()) == {"0", "1"}
        assert h5file["invalid_vector_channels/trace/0"][:].tolist() == [3.0, 4.0]
        assert h5file["invalid_vector_channels/trace/1"][:].tolist() == [4.0, 5.0]


def test_move_last_n_data_points_appends_across_retakes(tmp_path: Path) -> None:
    with h5py.File(tmp_path / "results.h5", "w") as h5file:
        _write_data_points(h5file, count=5)

        _move_last_n_data_points_to_invalid(h5file, no_data_points=2)
        # A second retake of more points than remain is clamped to what is left.
        moved = _move_last_n_data_points_to_invalid(h5file, no_data_points=10)

        assert moved == [0, 1, 2]
        assert h5file.attrs["number_of_data_points"] == 0
        assert h5file["scan_parameters"].shape == (0, 1)

        # Invalid datasets accumulate both batches.
        assert h5file["invalid_indices"][:].tolist() == [3, 4, 0, 1, 2]
        assert h5file["invalid_scan_parameters"].shape == (5, 1)
        # Vector datasets from the second batch use append positions 2, 3, 4.
        assert set(h5file["invalid_vector_channels/trace"].keys()) == {
            "0",
            "1",
            "2",
            "3",
            "4",
        }
        assert h5file["invalid_vector_channels/trace/2"][:].tolist() == [0.0, 1.0]


def test_move_last_n_data_points_noop_when_zero(tmp_path: Path) -> None:
    with h5py.File(tmp_path / "results.h5", "w") as h5file:
        _write_data_points(h5file, count=3)

        assert _move_last_n_data_points_to_invalid(h5file, no_data_points=0) == []
        assert h5file.attrs["number_of_data_points"] == 3
        assert "invalid_indices" not in h5file
