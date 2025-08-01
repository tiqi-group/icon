import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, TypedDict, cast

import h5py  # type: ignore
import numpy as np
import numpy.typing as npt
from filelock import FileLock

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.utils.h5py import get_hdf5_dtype
from icon.server.web_server.socketio_emit_queue import emit_queue

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class ResultDict(TypedDict):
    result_channels: dict[str, float]
    vector_channels: dict[str, list[float]]
    shot_channels: dict[str, list[int]]


class ExperimentDataPoint(ResultDict):
    index: int
    scan_params: dict[str, DatabaseValueType]
    timestamp: str
    sequence_json: str


class ExperimentData(TypedDict):
    shot_channels: dict[str, dict[int, list[int]]]
    result_channels: dict[str, dict[int, float]]
    vector_channels: dict[str, dict[int, list[float]]]
    scan_parameters: dict[str, dict[int, str | float]]
    json_sequences: list[list[int | str]]


def get_filename_by_job_id(job_id: int) -> str:
    scheduled_time = JobRunRepository.get_scheduled_time_by_job_id(job_id=job_id)
    return f"{scheduled_time}.h5"


def resize_dataset(dataset: h5py.Dataset, next_index: int, axis: int) -> None:
    dataset.resize(next_index + 1, axis)


def write_sequence_json_to_dataset(
    h5file: h5py.File,
    data_point_index: int,
    sequence_json: str,
) -> None:
    """Write scan parameters and timestamp to scan_parameters dataset."""

    sequence_json_dtype = [
        ("index", np.int32),
        ("Sequence", h5py.string_dtype()),
    ]
    sequence_json_dataset = h5file.require_dataset(
        "sequence_json",
        shape=(0,),
        maxshape=(None,),
        chunks=True,
        dtype=sequence_json_dtype,
        compression="gzip",
        compression_opts=9,
    )

    index = sequence_json_dataset.shape[0]
    if index > 0:
        _, sequence_json_old = cast(
            "tuple[int, bytes]", sequence_json_dataset[index - 1]
        )
        if sequence_json_old.decode() == sequence_json:
            logger.debug("Sequence JSON didn't change.")
            return

    resize_dataset(sequence_json_dataset, next_index=index, axis=0)

    sequence_json_dataset[index] = (data_point_index, sequence_json)


def write_scan_parameters_and_timestamp_to_dataset(
    h5file: h5py.File,
    data_point_index: int,
    scan_params: dict[str, DatabaseValueType],
    timestamp: str,
    number_of_data_points: int,
) -> None:
    """Write scan parameters and timestamp to scan_parameters dataset."""

    scan_parameter_dtype = [
        ("timestamp", "S26"),  # timestamps are strings of length 26
        *[(key, np.float64) for key in scan_params],
    ]
    scan_params_dataset = h5file.require_dataset(
        "scan_parameters",
        shape=(number_of_data_points, 1),
        maxshape=(None, 1),
        chunks=True,
        dtype=scan_parameter_dtype,
        compression="gzip",
        compression_opts=9,
    )

    if data_point_index >= number_of_data_points:
        resize_dataset(scan_params_dataset, next_index=data_point_index, axis=0)

    parameter_values = tuple(scan_params[key] for key in scan_params)
    scan_params_dataset[data_point_index] = (
        timestamp,
        *parameter_values,
    )


def write_results_to_dataset(
    h5file: h5py.File,
    data_point_index: int,
    result_channels: dict[str, float],
    number_of_data_points: int,
) -> None:
    """Write results to result_channels dataset."""

    sorted_keys = sorted(result_channels)
    result_dtype = np.dtype([(key, np.float64) for key in sorted_keys])

    result_dataset = h5file.require_dataset(
        "result_channels",
        shape=(number_of_data_points,),
        maxshape=(None,),
        chunks=True,
        dtype=result_dtype,
        compression="gzip",
        compression_opts=9,
    )

    if set(result_dataset.dtype.names) != set(sorted_keys):
        raise RuntimeError(
            f"Result channels changed from {list(result_dataset.dtype.names)} to "
            f"{sorted_keys}"
        )

    if data_point_index >= number_of_data_points:
        resize_dataset(result_dataset, next_index=data_point_index, axis=0)

    result_dataset[data_point_index] = tuple(result_channels[k] for k in sorted_keys)


def write_shot_channels_to_datasets(
    h5file: h5py.File,
    data_point_index: int,
    shot_channels: dict[str, list[int]],
    number_of_data_points: int,
    number_of_shots: int,
) -> None:
    """Write shot channel data into shot_channels group datasets."""

    shot_group = h5file.require_group("shot_channels")
    for key, value in shot_channels.items():
        shot_dataset = shot_group.require_dataset(
            key,
            shape=(number_of_data_points, number_of_shots),
            maxshape=(None, number_of_shots),
            chunks=True,
            dtype=np.float64,
            compression="gzip",
            compression_opts=9,
        )

        if data_point_index >= number_of_data_points:
            resize_dataset(shot_dataset, next_index=data_point_index, axis=0)
        shot_dataset[data_point_index] = value


def write_vector_channels_to_datasets(
    h5file: h5py.File,
    data_point_index: int,
    vector_channels: dict[str, list[float]],
) -> None:
    """Create a dataset for each vector channel and data point."""

    vector_group = h5file.require_group("vector_channels")
    for channel_name, vector in vector_channels.items():
        channel_group = vector_group.require_group(channel_name)
        if str(data_point_index) not in channel_group:
            channel_group.create_dataset(
                str(data_point_index),
                data=vector,
                compression="gzip",
                compression_opts=9,
            )


class ExperimentDataRepository:
    LOCK_EXTENSION = ".lock"

    @staticmethod
    def update_metadata_by_job_id(
        *,
        job_id: int,
        number_of_shots: int,
        repetitions: int,
        local_parameter_timestamp: datetime | None = None,
        parameters: list[ScanParameter] = [],
    ) -> None:
        """Creates or updates a metadata group and updates its attributes with the
        passed metadata."""

        filename = get_filename_by_job_id(job_id)
        file = f"{get_config().experiment_library.results_dir}/{filename}"

        job = JobRepository.get_job_by_id(job_id=job_id, load_experiment_source=True)

        lock_path = (
            f"{get_config().experiment_library.results_dir}/.{filename}"
            f"{ExperimentDataRepository.LOCK_EXTENSION}"
        )
        with FileLock(lock_path), h5py.File(file, "a") as h5file:
            h5file.attrs["number_of_data_points"] = 0
            h5file.attrs["number_of_shots"] = number_of_shots
            h5file.attrs["experiment_id"] = job.experiment_source.experiment_id
            h5file.attrs["job_id"] = job_id
            h5file.attrs["repetitions"] = repetitions
            if local_parameter_timestamp is not None:
                h5file.attrs["local_parameter_timestamp"] = local_parameter_timestamp

            scan_parameter_dtype = [
                ("timestamp", "S26"),
                *[(param.variable_id, np.float64) for param in parameters],
            ]
            h5file.create_dataset(
                "scan_parameters",
                shape=(0, 1),
                maxshape=(None, 1),
                chunks=True,
                dtype=scan_parameter_dtype,
                compression="gzip",
                compression_opts=9,
            )

            for parameter in parameters:
                if parameter.device is not None:
                    h5file["scan_parameters"].attrs[parameter.unique_id()] = (
                        f"name={parameter.device.name} url={parameter.device.url}"
                        f"description={parameter.device.description}"
                    )

    @staticmethod
    def write_experiment_data_by_job_id(
        *,
        job_id: int,
        data_point: ExperimentDataPoint,
    ) -> None:
        filename = get_filename_by_job_id(job_id)
        file = f"{get_config().experiment_library.results_dir}/{filename}"

        lock_path = (
            f"{get_config().experiment_library.results_dir}/.{filename}"
            f"{ExperimentDataRepository.LOCK_EXTENSION}"
        )
        with FileLock(lock_path), h5py.File(file, "a") as h5file:
            try:
                number_of_shots = cast("int", h5file.attrs["number_of_shots"])
                number_of_data_points = cast(
                    "int", h5file.attrs["number_of_data_points"]
                )
            except KeyError:
                raise Exception(
                    "Metadata does not contain relevant information. Please use "
                    "ExperimentDataRepository.update_metadata_by_job_id first!"
                )

            write_scan_parameters_and_timestamp_to_dataset(
                h5file=h5file,
                data_point_index=data_point["index"],
                scan_params=data_point["scan_params"],
                timestamp=data_point["timestamp"],
                number_of_data_points=number_of_data_points,
            )

            write_results_to_dataset(
                h5file=h5file,
                data_point_index=data_point["index"],
                result_channels=data_point["result_channels"],
                number_of_data_points=number_of_data_points,
            )

            write_shot_channels_to_datasets(
                h5file=h5file,
                data_point_index=data_point["index"],
                shot_channels=data_point["shot_channels"],
                number_of_data_points=number_of_data_points,
                number_of_shots=number_of_shots,
            )

            write_vector_channels_to_datasets(
                h5file=h5file,
                data_point_index=data_point["index"],
                vector_channels=data_point["vector_channels"],
            )

            write_sequence_json_to_dataset(
                h5file=h5file,
                data_point_index=data_point["index"],
                sequence_json=data_point["sequence_json"],
            )

            # increase the number of data points
            if data_point["index"] >= number_of_data_points:
                h5file.attrs["number_of_data_points"] = data_point["index"] + 1

            logger.debug("Appended data to %s", file)

        emit_queue.put(
            {
                "event": f"experiment_{job_id}",
                "data": data_point,
            }
        )

    @staticmethod
    def write_parameter_update_by_job_id(
        *,
        job_id: int,
        timestamp: str,
        parameter_values: dict[str, str | int | float | bool],
    ) -> None:
        """Write parameter updates to a dataset for each parameter under 'parameters'.
        Datasets contain (timestamp, value). Only appends if the value changed.
        """

        filename = get_filename_by_job_id(job_id)
        file = f"{get_config().experiment_library.results_dir}/{filename}"
        lock_path = (
            f"{get_config().experiment_library.results_dir}/.{filename}"
            f"{ExperimentDataRepository.LOCK_EXTENSION}"
        )

        with FileLock(lock_path), h5py.File(file, "a") as h5file:
            parameters_group = h5file.require_group("parameters")

            for param_id, value in parameter_values.items():
                dtype = [("timestamp", "S26"), ("value", get_hdf5_dtype(value))]

                if param_id in parameters_group:
                    ds = cast("h5py.Dataset", parameters_group[param_id])
                    if ds.shape[0] > 0:
                        last_entry = ds[-1]
                        last_value = last_entry["value"]
                        if isinstance(value, str):
                            if last_value.decode() == value:
                                continue
                        elif last_value == value:
                            continue

                    index = ds.shape[0]
                    resize_dataset(ds, next_index=index, axis=0)
                else:
                    ds = parameters_group.create_dataset(
                        param_id,
                        shape=(1,),
                        maxshape=(None,),
                        dtype=dtype,
                    )
                    index = 0

                ds[index] = (timestamp.encode(), value)

            logger.debug(
                "Wrote parameter update for job %d at %s",
                job_id,
                timestamp,
            )

    @staticmethod
    def get_experiment_data_by_job_id(
        *,
        job_id: int,
    ) -> ExperimentData:
        data: ExperimentData = {
            "shot_channels": {},
            "result_channels": {},
            "vector_channels": {},
            "scan_parameters": {},
            "json_sequences": [],
        }

        filename = get_filename_by_job_id(job_id)
        file = f"{get_config().experiment_library.results_dir}/{filename}"

        if not os.path.exists(file):
            raise FileNotFoundError(f"The file {file} does not exist.")

        lock_path = (
            f"{get_config().experiment_library.results_dir}/.{filename}"
            f"{ExperimentDataRepository.LOCK_EXTENSION}"
        )
        with FileLock(lock_path), h5py.File(file, "r") as h5file:
            # Parse JSON strings in relevant columns back into Python objects

            scan_parameters: npt.NDArray = h5file["scan_parameters"][:]  # type: ignore
            data["scan_parameters"] = {
                param: {
                    index: value[0]
                    .item()
                    .decode()  # converting timestamp bytes to string
                    if isinstance(value[0], np.bytes_)
                    else value[0].item()  # value is stored as a list with one entry
                    for index, value in enumerate(scan_parameters[param])
                }
                for param in cast("tuple[str, ...]", scan_parameters.dtype.names)
            }

            result_channels: npt.NDArray = h5file["result_channels"][:]  # type: ignore
            data["result_channels"] = {
                channel_name: dict(
                    enumerate(
                        cast("list[float]", result_channels[channel_name].tolist())
                    )
                )
                for channel_name in cast("tuple[str, ...]", result_channels.dtype.names)
            }

            # Convert shot channels into dicts with index as key
            shot_channels_group = cast("h5py.Group", h5file["shot_channels"])
            data["shot_channels"] = {
                key: dict(enumerate(value[:].tolist()))  # type: ignore
                for key, value in cast(
                    "Sequence[tuple[str, h5py.Dataset]]", shot_channels_group.items()
                )
            }

            vector_channels_group = cast("h5py.Group", h5file["vector_channels"])
            data["vector_channels"] = {
                channel_name: {
                    int(data_point): vector_dataset[:].tolist()
                    for data_point, vector_dataset in cast(
                        "Sequence[tuple[str, h5py.Dataset]]", vector_group.items()
                    )
                }
                for channel_name, vector_group in cast(
                    "Sequence[tuple[str, h5py.Group]]", vector_channels_group.items()
                )
            }

            sequence_json_dataset = cast("h5py.Dataset", h5file["sequence_json"])
            data["json_sequences"] = [
                [cast("np.int32", entry["index"]).item(), entry["Sequence"].decode()]
                for entry in sequence_json_dataset
            ]
            return data
