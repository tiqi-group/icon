import json
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Literal, TypedDict, cast

import h5py  # type: ignore
import numpy as np
import numpy.typing as npt
from filelock import FileLock

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.data_access.models.sqlite.scan_parameter import (
    ScanParameter,
    contains_realtime_parameter,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.utils.h5py import get_hdf5_dtype, get_result_channels_dataset
from icon.server.web_server.socketio_emit_queue import emit_queue

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class ResultDict(TypedDict):
    """Scalar/vector/shot readouts for a single data point."""

    result_channels: dict[str, float]
    """Mapping from result channel name to scalar value."""
    vector_channels: dict[str, list[float]]
    """Mapping from vector channel name to list of floats."""
    shot_channels: dict[str, list[int]]
    """Mapping from shot channel name to per-shot integers."""


class ExperimentDataPoint(ResultDict):
    """A single data point with its context."""

    index: int
    """Sequential index of this data point."""
    scan_params: dict[str, DatabaseValueType]
    """Parameter values that produced this data point."""
    timestamp: str
    """Acquisition timestamp (ISO string)."""
    sequence_json: str
    """Serialized sequence JSON used for this data point."""


class PlotWindowMetadata(TypedDict):
    """Metadata describing a single plot window for visualization in the frontend.

    This metadata includes the plot's index within its type, the type of plot (e.g.,
    vector, histogram, or readout), and the list of channel names that are to be plotted
    in the respective window.
    """

    name: str
    """The name of the plot window"""
    index: int
    """The order of the plot window within its type (e.g., 0, 1, 2...)"""
    type: Literal["vector", "histogram", "readout"]
    """The type of the plot window"""
    channel_names: list[str]
    """A list of channel names to be plotted in this window"""


class ReadoutMetadata(TypedDict):
    """Metadata describing readout/shot/vector channels and their plot windows."""

    readout_channel_names: list[str]
    """A list of all readout channel names"""
    shot_channel_names: list[str]
    """A list of all shot channel names"""
    vector_channel_names: list[str]
    """A list of all vector channel names"""
    readout_channel_windows: list[PlotWindowMetadata]
    """List of `PlotWindowMetadata` of result channels"""
    shot_channel_windows: list[PlotWindowMetadata]
    """List of `PlotWindowMetadata` of shot channels"""
    vector_channel_windows: list[PlotWindowMetadata]
    """List of `PlotWindowMetadata` of vector channels"""


class PlotWindowsDict(TypedDict):
    """Grouping of plot window metadata by channel type."""

    result_channels: list[PlotWindowMetadata]
    """Plot window metadata for result channels."""
    shot_channels: list[PlotWindowMetadata]
    """Plot window metadata for shot channels."""
    vector_channels: list[PlotWindowMetadata]
    """Plot window metadata for vector channels."""


class ExperimentData(TypedDict):
    """Container for all experiment data returned to the API."""

    plot_windows: PlotWindowsDict
    """Plot window metadata grouped by channel class."""
    shot_channels: dict[str, dict[int, list[int]]]
    """Shot channels as channel_name -> {index -> values}."""
    result_channels: dict[str, dict[int, float]]
    """Result channels as channel_name -> {index -> value}."""
    vector_channels: dict[str, dict[int, list[float]]]
    """Vector channels as channel_name -> {index -> values}."""
    scan_parameters: dict[str, dict[int, str | float]]
    """Scan parameters as param_id -> {index -> value/timestamp}."""
    json_sequences: list[list[int | str]]
    """List of [index, sequence_json] pairs (list for pydase JSON compatibility)."""
    realtime_scan: bool
    """True if the experiment has a realtime scan parameter."""


def get_filename_by_job_id(job_id: int) -> str:
    """Return the HDF5 filename for a job.

    Args:
        job_id: Job identifier.

    Returns:
        Filename derived from the job's scheduled time (e.g., "<iso>.h5").
    """

    scheduled_time = JobRunRepository.get_scheduled_time_by_job_id(job_id=job_id)
    return f"{scheduled_time}.h5"


def resize_dataset(dataset: h5py.Dataset, next_index: int, axis: int) -> None:
    """Resize a dataset to accommodate writing at a target index.

    Args:
        dataset: HDF5 dataset to resize.
        next_index: Index that must be writable.
        axis: Axis along which to grow.
    """

    dataset.resize(next_index + 1, axis)


def write_sequence_json_to_dataset(
    h5file: h5py.File,
    data_point_index: int,
    sequence_json: str,
) -> None:
    """Append sequence JSON if it changed since the last entry.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        sequence_json: Serialized sequence JSON to append.
    """

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
    """Write scan parameters and timestamp to the 'scan_parameters' dataset.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        scan_params: Parameter values for this data point.
        timestamp: Acquisition timestamp (ISO string).
        number_of_data_points: Current total number of stored data points.
    """

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
    """Write scalar result channels into the 'result_channels' dataset.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        result_channels: Mapping of channel name to float value.
        number_of_data_points: Current total number of stored data points.
    """

    if not result_channels:
        return

    sorted_keys = sorted(result_channels)

    result_dataset = get_result_channels_dataset(
        h5file=h5file,
        result_channels=sorted_keys,
        number_of_data_points=number_of_data_points,
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
    """Write per-shot data into datasets under the 'shot_channels' group.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        shot_channels: Mapping of channel to per-shot integers.
        number_of_data_points: Current total number of stored data points.
        number_of_shots: Expected number of shots per channel.
    """

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
    """Write vector channel data under the 'vector_channels' group.

    Creates one dataset per channel per data point.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        vector_channels: Mapping of channel to vector of floats.
    """

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
    """Repository for HDF5-based experiment data.

    Manages HDF5 file creation and updates (metadata, results, parameters), with
    file-level locking to support concurrent writers.
    """

    LOCK_EXTENSION = ".lock"

    @staticmethod
    def update_metadata_by_job_id(  # noqa: PLR0913
        *,
        job_id: int,
        number_of_shots: int,
        repetitions: int,
        readout_metadata: ReadoutMetadata,
        local_parameter_timestamp: datetime | None = None,
        parameters: list[ScanParameter] = [],
    ) -> None:
        """Create or update HDF5 metadata for a job.

        Initializes datasets, sets file-level attributes, and stores plot window
        metadata for result/shot/vector channels.

        Args:
            job_id: Job identifier.
            number_of_shots: Shots per data point.
            repetitions: Number of repetitions.
            readout_metadata: Plot/window/channel metadata.
            local_parameter_timestamp: Optional timestamp for local parameters.
            parameters: Scan parameters.
        """

        filename = get_filename_by_job_id(job_id)
        file = f"{get_config().data.results_dir}/{filename}"

        job = JobRepository.get_job_by_id(job_id=job_id, load_experiment_source=True)

        lock_path = (
            f"{get_config().data.results_dir}/.{filename}"
            f"{ExperimentDataRepository.LOCK_EXTENSION}"
        )
        with FileLock(lock_path), h5py.File(file, "a") as h5file:
            h5file.attrs["number_of_data_points"] = 0
            h5file.attrs["number_of_shots"] = number_of_shots
            h5file.attrs["experiment_id"] = job.experiment_source.experiment_id
            h5file.attrs["job_id"] = job_id
            h5file.attrs["repetitions"] = repetitions
            h5file.attrs["realtime_scan"] = contains_realtime_parameter(parameters)

            if local_parameter_timestamp is not None:
                h5file.attrs["local_parameter_timestamp"] = local_parameter_timestamp

            scan_parameter_dtype = [
                ("timestamp", "S26"),
                *[
                    (param.variable_id, np.float64)
                    for param in parameters
                    if not param.realtime
                ],
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

            if readout_metadata["readout_channel_names"]:
                result_dataset = get_result_channels_dataset(
                    h5file=h5file, result_channels=readout_metadata["readout_channel_names"]
                )
                result_dataset.attrs["Plot window metadata"] = json.dumps(
                    readout_metadata["readout_channel_windows"]
                )

            if readout_metadata["shot_channel_names"]:
                shot_group = h5file.require_group("shot_channels")
                shot_group.attrs["Plot window metadata"] = json.dumps(
                    readout_metadata["shot_channel_windows"]
                )

            if readout_metadata["vector_channel_names"]:
                vector_group = h5file.require_group("vector_channels")
                vector_group.attrs["Plot window metadata"] = json.dumps(
                    readout_metadata["vector_channel_windows"]
                )

        emit_queue.put(
            {
                "event": f"experiment_{job_id}_metadata",
                "data": {
                    "readout_metadata": {
                        "result_channels": readout_metadata["readout_channel_windows"],
                        "shot_channels": readout_metadata["shot_channel_windows"],
                        "vector_channels": readout_metadata["vector_channel_windows"],
                    },
                },
            }
        )

    @staticmethod
    def write_experiment_data_by_job_id(
        *,
        job_id: int,
        data_point: ExperimentDataPoint,
    ) -> None:
        """Append a complete data point to the HDF5 file and emit an event.

        Writes scan parameters, result/shot/vector channels, and sequence JSON.

        Args:
            job_id: Job identifier.
            data_point: Data point payload to append.
        """

        filename = get_filename_by_job_id(job_id)
        file = f"{get_config().data.results_dir}/{filename}"

        lock_path = (
            f"{get_config().data.results_dir}/.{filename}"
            f"{ExperimentDataRepository.LOCK_EXTENSION}"
        )
        with FileLock(lock_path), h5py.File(file, "a") as h5file:
            try:
                number_of_shots: int = h5file.attrs["number_of_shots"]
                number_of_data_points: int = h5file.attrs["number_of_data_points"]
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
        """Append parameter updates under the 'parameters' group.

        Creates a dataset per parameter storing (timestamp, value) entries.
        Appends only when the value changed from the last entry.

        Args:
            job_id: Job identifier.
            timestamp: ISO timestamp string.
            parameter_values: Mapping of parameter id to value.
        """

        filename = get_filename_by_job_id(job_id)
        file = f"{get_config().data.results_dir}/{filename}"
        lock_path = (
            f"{get_config().data.results_dir}/.{filename}"
            f"{ExperimentDataRepository.LOCK_EXTENSION}"
        )

        with FileLock(lock_path), h5py.File(file, "a") as h5file:
            parameters_group = h5file.require_group("parameters")

            for param_id, value in parameter_values.items():
                dtype = [("timestamp", "S26"), ("value", get_hdf5_dtype(value))]

                if param_id in parameters_group:
                    ds: h5py.Dataset = parameters_group[param_id]
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
        """Load all stored data for a job from its HDF5 file.

        Args:
            job_id: Job identifier.

        Returns:
            Experiment data payload suitable for the API.
        """

        data: ExperimentData = {
            "plot_windows": {
                "result_channels": [],
                "shot_channels": [],
                "vector_channels": [],
            },
            "shot_channels": {},
            "result_channels": {},
            "vector_channels": {},
            "scan_parameters": {},
            "json_sequences": [],
            "realtime_scan": False,
        }

        filename = get_filename_by_job_id(job_id)
        file = f"{get_config().data.results_dir}/{filename}"

        if not os.path.exists(file):
            logger.warning("The file %s does not exist.", file)
            return data

        lock_path = (
            f"{get_config().data.results_dir}/.{filename}"
            f"{ExperimentDataRepository.LOCK_EXTENSION}"
        )
        with FileLock(lock_path), h5py.File(file, "r") as h5file:
            data["realtime_scan"] = bool(h5file.attrs["realtime_scan"])
            # Parse JSON strings in relevant columns back into Python objects

            scan_parameters: npt.NDArray = h5file["scan_parameters"][:]  # type: ignore
            data["scan_parameters"] = {
                param: {
                    index: value[0].item().decode()
                    if isinstance(value[0], np.bytes_)
                    else value[0].item()
                    for index, value in enumerate(scan_parameters[param])
                }
                for param in cast("tuple[str, ...]", scan_parameters.dtype.names)
            }

            if "result_channels" in h5file:
                result_channel_dataset = cast("h5py.Dataset", h5file["result_channels"])
                data["plot_windows"]["result_channels"] = json.loads(
                    cast("str", result_channel_dataset.attrs["Plot window metadata"])
                )
                result_channels = cast("npt.NDArray", result_channel_dataset[:])  # type: ignore
                data["result_channels"] = {
                    channel_name: dict(
                        enumerate(
                            cast("list[float]", result_channels[channel_name].tolist())
                        )
                    )
                    for channel_name in cast("tuple[str, ...]", result_channels.dtype.names)
                }
            else:
                data["plot_windows"]["result_channels"] = []
                data["result_channels"] = {}

            # Convert shot channels into dicts with index as key
            if "shot_channels" in h5file:
                shot_channels_group = cast("h5py.Group", h5file["shot_channels"])
                data["plot_windows"]["shot_channels"] = json.loads(
                    cast("str", shot_channels_group.attrs["Plot window metadata"])
                )
                data["shot_channels"] = {
                    key: dict(enumerate(value[:].tolist()))  # type: ignore
                    for key, value in cast(
                        "Sequence[tuple[str, h5py.Dataset]]", shot_channels_group.items()
                    )
                }
            else:
                data["plot_windows"]["shot_channels"] = []
                data["shot_channels"] = {}

            if "vector_channels" in h5file:
                vector_channels_group = cast("h5py.Group", h5file["vector_channels"])
                data["plot_windows"]["vector_channels"] = json.loads(
                    cast("str", vector_channels_group.attrs["Plot window metadata"])
                )
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
            else:
                data["plot_windows"]["vector_channels"] = []
                data["vector_channels"] = {}

            sequence_json_dataset = cast("h5py.Dataset", h5file["sequence_json"])
            data["json_sequences"] = [
                [cast("np.int32", entry["index"]).item(), entry["Sequence"].decode()]
                for entry in sequence_json_dataset
            ]
            return data
