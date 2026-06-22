import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import h5py  # type: ignore
import numpy as np
import numpy.typing as npt

from icon.config.config import get_config
from icon.server.data_access.experiment_data import (
    DatabaseValueType,
    ExperimentData,
    ExperimentDataPoint,
    ExperimentDeviceData,
    FitResult,
    ParameterValue,
    PlotWindowMetadata,
    ReadoutMetadata,
)
from icon.server.data_access.models.sqlite.scan_parameter import (
    ScanParameter,
    contains_realtime_parameter,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.web_server.socketio_emit_queue import emit_queue

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


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


def write_hardware_instructions_to_dataset(
    h5file: h5py.File,
    data_point_index: int,
    device_id: str,
    hardware_instructions: bytes,
) -> None:
    """Append hardware instructions if it changed since the last entry.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        device_id: Identifier of the device the hardware instructions are created for.
        hardware_instructions: Serialized hardware instructions to append.
    """
    hw_instructions_dtype = [
        ("index", np.int32),
        ("Sequence", h5py.string_dtype()),
    ]
    hw_instructions_dataset = h5file.require_group(
        "hardware_instructions"
    ).require_dataset(
        device_id,
        shape=(0,),
        maxshape=(None,),
        chunks=True,
        dtype=hw_instructions_dtype,
        compression="gzip",
        compression_opts=9,
    )

    index = hw_instructions_dataset.shape[0]
    if index > 0:
        _, hw_instructions_old = cast(
            "tuple[int, bytes]", hw_instructions_dataset[index - 1]
        )
        if hw_instructions_old.decode() == hardware_instructions:
            logger.debug("Hardware instructions didn't change.")
            return

    resize_dataset(hw_instructions_dataset, next_index=index, axis=0)

    hw_instructions_dataset[index] = (
        data_point_index,
        hardware_instructions,
    )


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
    device_id: str,
    number_of_data_points: int,
) -> None:
    """Write scalar result channels into the 'result_channels' dataset.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        result_channels: Mapping of channel name to float value.
        device_id: ID of the device the data was read out from.
        number_of_data_points: Current total number of stored data points.
    """
    if not result_channels:
        return

    sorted_keys = sorted(result_channels)

    result_dataset = get_result_channels_dataset(
        h5file=h5file,
        result_channels=sorted_keys,
        device_id=device_id,
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
    device_id: str,
    shot_channels: dict[str, list[int]],
    number_of_data_points: int,
    number_of_shots: int,
) -> None:
    """Write per-shot data into datasets under the 'shot_channels' group.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        device_id: ID of the device this data is coming from.
        shot_channels: Mapping of channel to per-shot integers.
        number_of_data_points: Current total number of stored data points.
        number_of_shots: Expected number of shots per channel.
    """
    shot_group = h5file.require_group("shot_channels").require_group(device_id)
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
    device_id: str,
    vector_channels: dict[str, list[float]],
) -> None:
    """Write vector channel data under the 'vector_channels' group.

    Creates one dataset per channel per data point.

    Args:
        h5file: Open HDF5 file handle.
        device_id: ID of the device this data is coming from.
        data_point_index: Index of the current data point.
        vector_channels: Mapping of channel to vector of floats.
    """
    vector_group = h5file.require_group("vector_channels").require_group(device_id)
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
    hdf5-level locking to support concurrent writers.
    """

    @staticmethod
    def update_metadata_by_job_id(
        *,
        job_id: int,
        number_of_shots: int,
        repetitions: int,
        readout_metadata: list[tuple[str, ReadoutMetadata]],
        local_parameter_timestamp: datetime | None = None,
        parameters: list[ScanParameter] | None = None,
    ) -> None:
        """Create or update HDF5 metadata for a job.

        Initializes datasets, sets file-level attributes, and stores plot window
        metadata for result/shot/vector channels.

        Args:
            job_id: Job identifier.
            device_id: ID of the device the metadata is about.
            number_of_shots: Shots per data point.
            repetitions: Number of repetitions.
            readout_metadata: Plot/window/channel metadata per device (device_id, metadata pairs).
            local_parameter_timestamp: Optional timestamp for local parameters.
            parameters: Scan parameters.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename
        job = JobRepository.get_job_by_id(job_id=job_id, load_experiment_source=True)

        with h5_open(h5_path, "a") as h5file:
            prepare_readout_metadata(
                h5file,
                job_id=job_id,
                experiment_id=job.experiment_source.experiment_id,
                number_of_shots=number_of_shots,
                repetitions=repetitions,
                readout_metadata=readout_metadata,
                local_parameter_timestamp=local_parameter_timestamp,
                parameters=parameters or [],
            )

        metadata_key_remap = {
            "readout_channel_windows": "result_channels",
            "shot_channel_windows": "shot_channels",
            "vector_channel_windows": "vector_channels",
        }
        emit_queue.put(
            {
                "event": f"experiment_{job_id}_metadata",
                "data": [
                    {
                        "device_id": device_id,
                        "readout_metadata": {
                            metadata_key_remap[key]: val
                            for key, val in asdict(metadata).items()
                            if key in metadata_key_remap
                        },
                    }
                    for device_id, metadata in readout_metadata
                ],
            }
        )

    @staticmethod
    def write_experiment_data_by_job_id(
        *,
        job_id: int,
        data_point: ExperimentDataPoint,
    ) -> None:
        """Append a complete data point to the HDF5 file and emit an event.

        Writes scan parameters, result/shot/vector channels, and hardware instructions.

        Args:
            job_id: Job identifier.
            data_point: Data point payload to append.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename

        with h5_open(h5_path, "a") as h5file:
            write_experiment_data_point(h5file, data_point)
        logger.debug("Appended data to %s", h5_path)

        emit_queue.put(
            {
                "event": f"experiment_{job_id}",
                "data": data_point.serialize(),
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
        h5_path = Path(get_config().data.results_dir) / filename
        parameter_updates = {}
        with h5_open(h5_path, "a") as h5file:
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
                parameter_updates[param_id] = ParameterValue(timestamp, value)

            logger.debug(
                "Wrote parameter update for job %d at %s",
                job_id,
                timestamp,
            )
        emit_queue.put(
            {
                "event": f"experiment_params_{job_id}",
                "data": {
                    param_id: asdict(val) for param_id, val in parameter_updates.items()
                },
            }
        )

    @staticmethod
    def get_experiment_data_by_job_id(
        *,
        job_id: int,
        max_transfer_bytes: int = 50_000_000,
    ) -> ExperimentData:
        """Load stored data for a job from its HDF5 file.

        When loading all data would exceed *max_transfer_bytes*, only the
        last N data points that fit within the budget are returned.  The
        budget is estimated from HDF5 metadata (channel count, shots per
        channel) without reading actual data.

        Args:
            job_id: Job identifier.
            max_transfer_bytes: Approximate cap on the serialised payload
                size in bytes.  Defaults to 50 MB.

        Returns:
            Experiment data payload suitable for the API.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename

        if not Path(h5_path).exists():
            logger.warning("The file %s does not exist.", h5_path)
            return ExperimentData()

        with h5_open(h5_path, "r") as h5file:
            return load_experiment_data(h5file, max_transfer_bytes)


def prepare_readout_metadata(
    h5file: h5py.File,
    *,
    job_id: int,
    experiment_id: int,
    number_of_shots: int,
    repetitions: int,
    readout_metadata: list[tuple[str, ReadoutMetadata]],
    local_parameter_timestamp: datetime | None,
    parameters: list[ScanParameter],
) -> None:
    h5file.attrs["number_of_data_points"] = 0
    h5file.attrs["number_of_shots"] = number_of_shots
    h5file.attrs["experiment_id"] = experiment_id
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

    for device_id, metadata in readout_metadata:
        if metadata.readout_channel_names:
            result_dataset = get_result_channels_dataset(
                h5file=h5file,
                device_id=device_id,
                result_channels=metadata.readout_channel_names,
            )
            result_dataset.attrs["Plot window metadata"] = json.dumps(
                [asdict(w) for w in metadata.readout_channel_windows]
            )

        shot_group = h5file.require_group("shot_channels").require_group(device_id)
        shot_group.attrs["Plot window metadata"] = json.dumps(
            [asdict(w) for w in metadata.shot_channel_windows]
        )

        vector_group = h5file.require_group("vector_channels").require_group(device_id)
        vector_group.attrs["Plot window metadata"] = json.dumps(
            [asdict(w) for w in metadata.vector_channel_windows]
        )


def write_experiment_data_point(
    h5file: h5py.File, data_point: ExperimentDataPoint
) -> None:
    try:
        number_of_shots: int = h5file.attrs["number_of_shots"]
        number_of_data_points: int = h5file.attrs["number_of_data_points"]
    except KeyError:
        raise KeyError(
            "Metadata does not contain relevant information. Please use "
            "ExperimentDataRepository.update_metadata_by_job_id first!"
        ) from None

    write_scan_parameters_and_timestamp_to_dataset(
        h5file=h5file,
        data_point_index=data_point.index,
        scan_params=data_point.scan_params,
        timestamp=data_point.timestamp,
        number_of_data_points=number_of_data_points,
    )
    for device_data in data_point.device_data:
        write_results_to_dataset(
            h5file=h5file,
            data_point_index=data_point.index,
            device_id=device_data.device_id,
            result_channels=device_data.readouts.result_channels,
            number_of_data_points=number_of_data_points,
        )

        write_shot_channels_to_datasets(
            h5file=h5file,
            data_point_index=data_point.index,
            device_id=device_data.device_id,
            shot_channels=device_data.readouts.shot_channels,
            number_of_data_points=number_of_data_points,
            number_of_shots=number_of_shots,
        )

        write_vector_channels_to_datasets(
            h5file=h5file,
            device_id=device_data.device_id,
            data_point_index=data_point.index,
            vector_channels=device_data.readouts.vector_channels,
        )

        write_hardware_instructions_to_dataset(
            h5file=h5file,
            data_point_index=data_point.index,
            device_id=device_data.device_id,
            hardware_instructions=device_data.hardware_instructions,
        )

    if data_point.index >= number_of_data_points:
        h5file.attrs["number_of_data_points"] = data_point.index + 1


def load_experiment_data(  # noqa: C901
    h5file: h5py.File,
    max_transfer_bytes: int = 50_000_000,
) -> ExperimentData:
    """Load stored data for a job from its HDF5 file.

    When loading all data would exceed *max_transfer_bytes*, only the
    last N data points that fit within the budget are returned.  The
    budget is estimated from HDF5 metadata (channel count, shots per
    channel) without reading actual data.

    Args:
        h5file: File to load from.
        max_transfer_bytes: Approximate cap on the serialised payload
            size in bytes.  Defaults to 50 MB.

    Returns:
        Experiment data payload suitable for the API.
    """
    total = int(h5file.attrs.get("number_of_data_points", 0))
    data = ExperimentData(
        realtime_scan=bool(h5file.attrs.get("realtime_scan", False)),
        total_data_points=total,
    )
    shot_channels_groups: list[tuple[str, h5py.Group]] = list(
        h5file.get("shot_channels", {}).items()
    )
    result_channel_datasets = list(h5file.get("result_channels", {}).items())
    scan_parameters: h5py.Dataset | None = h5file.get("scan_parameters")
    vector_channels_groups: list[tuple[str, h5py.Group]] = list(
        h5file.get("vector_channels", {}).items()
    )

    # Estimate bytes per data point from HDF5 metadata
    bytes_per_point = estimate_bytes_per_data_point(
        total,
        shot_channels_groups,
        result_channel_datasets,
        vector_channels_groups,
    )

    max_data_points = max_transfer_bytes // bytes_per_point
    start_index = max(0, total - max_data_points)
    if start_index > 0:
        logger.info(
            "Loading last %d of %d data points (~%d bytes/point, %d MB budget)",
            total - start_index,
            total,
            bytes_per_point,
            max_transfer_bytes // 1_000_000,
        )

    if scan_parameters is not None:
        scan_parameters: npt.NDArray = scan_parameters[start_index:]  # type: ignore
        data.scan_parameters = {
            param: {
                start_index + i: value[0].item().decode()
                if isinstance(value[0], np.bytes_)
                else value[0].item()
                for i, value in enumerate(scan_parameters[param])
            }
            for param in cast("tuple[str, ...]", scan_parameters.dtype.names)
        }
    device_data: dict[str, ExperimentDeviceData] = {}

    for device_id, result_channel_dataset in result_channel_datasets:
        plot_metadata: str | None = result_channel_dataset.attrs.get(
            "Plot window metadata"
        )
        d = device_data.setdefault(device_id, ExperimentDeviceData(device_id))
        if plot_metadata:
            d.plot_windows.result_channels = [
                PlotWindowMetadata(**w) for w in json.loads(plot_metadata)
            ]
        result_channels = cast("npt.NDArray[Any]", result_channel_dataset[start_index:])  # type: ignore
        d.readouts.result_channels = {
            channel_name: dict(
                enumerate(
                    cast("list[float]", result_channels[channel_name].tolist()),
                    start=start_index,
                )
            )
            for channel_name in cast("tuple[str, ...]", result_channels.dtype.names)
        }

    # Convert shot channels into dicts with index as key
    for device_id, shot_channels_group in shot_channels_groups:
        plot_metadata = shot_channels_group.attrs.get("Plot window metadata")
        d = device_data.setdefault(device_id, ExperimentDeviceData(device_id))
        if plot_metadata:
            d.plot_windows.shot_channels = [
                PlotWindowMetadata(**w) for w in json.loads(plot_metadata)
            ]
        d.readouts.shot_channels = {
            key: dict(enumerate(value[start_index:].tolist(), start=start_index))  # type: ignore
            for key, value in cast(
                "Sequence[tuple[str, h5py.Dataset]]",
                shot_channels_group.items(),
            )
        }

    for device_id, vector_channels_group in vector_channels_groups:
        plot_metadata_s: str = vector_channels_group.attrs.get(
            "Plot window metadata", "[]"
        )
        d = device_data.setdefault(device_id, ExperimentDeviceData(device_id))
        d.plot_windows.vector_channels = [
            PlotWindowMetadata(**w) for w in json.loads(plot_metadata_s)
        ]
        d.readouts.vector_channels = {
            channel_name: {
                int(data_point): vector_dataset[:].tolist()
                for data_point, vector_dataset in cast(
                    "Sequence[tuple[str, h5py.Dataset]]", vector_group.items()
                )
            }
            for channel_name, vector_group in cast(
                "Sequence[tuple[str, h5py.Group]]",
                vector_channels_group.items(),
            )
        }

    hw_instruction_dataset: list[tuple[str, h5py.Dataset]] = list(
        h5file.get("hardware_instructions", {}).items()
    )
    fits = _read_fits_from_hdf5(h5file)
    for device_id, hw_instructions in hw_instruction_dataset:
        d = device_data.setdefault(device_id, ExperimentDeviceData(device_id))
        d.fits = fits.get(device_id, {})
        d.hardware_instructions = [
            (cast("np.int32", entry["index"]).item(), entry["Sequence"])
            for entry in hw_instructions
        ]
    data.parameters = extract_parameter_values(h5file)
    data.device_data = list(device_data.values())
    return data


def extract_parameter_values(
    h5file: h5py.File,
) -> dict[str, ParameterValue]:
    def last_value(d: h5py.Dataset) -> ParameterValue:
        ts, val = d[-1].tolist()
        if isinstance(val, bytes):
            val = val.decode()
        return ParameterValue(timestamp=ts.decode(), value=val)

    parameters_group = h5file.get("parameters")
    if parameters_group is None:
        return {}

    # param_ids may contain '/' which h5py treats as path separators, creating
    # nested groups instead of flat datasets — use visititems to collect all leaves
    result: dict[str, ParameterValue] = {}

    def visitor(name: str, obj: h5py.HLObject) -> None:
        if isinstance(obj, h5py.Dataset):
            result[name] = last_value(obj)

    parameters_group.visititems(visitor)
    return result


def get_hdf5_dtype(
    value: str | float | bool,  # noqa: FBT001
) -> type[np.float64 | np.bool | np.int64] | h5py.Datatype:
    """Return the HDF5-compatible dtype."""
    if isinstance(value, str):
        return h5py.string_dtype()
    if isinstance(value, bool):
        return np.bool
    if isinstance(value, int):
        return np.int64
    if isinstance(value, float):
        return np.float64

    raise TypeError(f"Unsupported parameter type: {type(value)}")


def get_result_channels_dataset(
    h5file: h5py.File,
    result_channels: list[str],
    device_id: str,
    number_of_data_points: int = 1,
) -> h5py.Dataset:
    sorted_result_channels = sorted(result_channels)
    result_dtype = np.dtype([(key, np.float64) for key in sorted_result_channels])

    return h5file.require_group("result_channels").require_dataset(
        device_id,
        shape=(number_of_data_points,),
        maxshape=(None,),
        chunks=True,
        dtype=result_dtype,
        compression="gzip",
        compression_opts=9,
    )


POLL_INTERVAL = 0.05


@contextmanager
def h5_open(path: Path, mode: str, **kwargs: Any) -> Iterator[h5py.File]:
    while True:
        try:
            with h5py.File(str(path), mode, **kwargs) as h5file:
                yield h5file
            break
        except (OSError, FileNotFoundError):
            time.sleep(POLL_INTERVAL)


def _read_fits_from_hdf5(
    h5file: h5py.File,
) -> dict[str, dict[str, FitResult]]:
    """Read all fit results from an HDF5 file."""
    if "fits" not in h5file:
        return {}

    fits: dict[str, dict[str, FitResult]] = {}
    fits_group = cast("h5py.Group", h5file["fits"])
    for device_id, device in fits_group.items():
        for channel_name, channel_group in device.items():
            fit_data = FitResult(
                **json.loads(cast("str", channel_group.attrs["fit_result"]))
            )
            fits.setdefault(device_id, {})[channel_name] = fit_data
    return fits


def write_fit_result_by_job_id(
    *,
    job_id: int,
    fit_results: list[tuple[str, FitResult]],
) -> None:
    """Write a fit result into the HDF5 file for a job.

    Creates or overwrites the ``fits/<result_channel>`` group.

    Args:
        job_id: Job identifier.
        fit_results: The fit result to persist (device_id, FitResult tuples).
    """
    filename = get_filename_by_job_id(job_id)
    h5_path = Path(get_config().data.results_dir) / filename
    with h5_open(h5_path, "a") as h5file:
        for device_id, fit_result in fit_results:
            fits_group = h5file.require_group("fits").require_group(device_id)
            channel = fit_result.result_channel
            if channel in fits_group:
                del fits_group[channel]
            grp = fits_group.create_group(channel)
            grp.attrs["fit_result"] = json.dumps(asdict(fit_result))


def get_fit_results_by_job_id(*, job_id: int) -> dict[str, dict[str, FitResult]]:
    """Read all fit results for a job from its HDF5 file.

    Args:
        job_id: Job identifier.

    Returns:
        Dict mapping result channel names to their fit result dicts.
    """
    filename = get_filename_by_job_id(job_id)
    h5_path = Path(get_config().data.results_dir) / filename
    if not h5_path.exists():
        return {}

    with h5_open(h5_path, "r") as h5file:
        return _read_fits_from_hdf5(h5file)


def delete_fit_result_by_job_id(
    *, job_id: int, result_channel: str, device_id: str
) -> None:
    """Delete a fit result for a specific channel from the HDF5 file.

    Args:
        job_id: Job identifier.
        result_channel: Name of the result channel whose fit to delete.
        device_id: ID of the device for which to delete the fits
    """
    filename = get_filename_by_job_id(job_id)
    h5_path = Path(get_config().data.results_dir) / filename
    with h5_open(h5_path, "a") as h5file:
        fits = h5file.get("fits", {}).get(device_id)
        if fits is not None and result_channel in fits:
            del fits[result_channel]


def estimate_bytes_per_data_point(
    total: int,
    shot_channels_groups: list[tuple[str, h5py.Group]],
    result_channel_datasets: list[tuple[str, h5py.Group]],
    vector_channels_groups: list[tuple[str, h5py.Group]],
) -> int:
    """Estimate bytes per data point from HDF5 metadata.

    Return total number of data points in `h5file` and estimated bytes per data point.
    """
    bytes_per_point = sum(
        ds.shape[1] * ds.dtype.itemsize
        for _, device in shot_channels_groups
        for ds in device.values()
    ) + sum(
        ds.dtype.itemsize
        for _, device in result_channel_datasets
        for ds in device
        if ds is not None
    )

    # Add vector channel size (average across all data points)
    total_vector_bytes = sum(
        dataset.shape[0] * dataset.dtype.itemsize
        for _, device in vector_channels_groups
        for channel_group in device.values()
        for dataset in channel_group.values()
    )
    if total > 0:
        bytes_per_point += total_vector_bytes // total
    # JSON serialisation roughly doubles the raw size
    return max(bytes_per_point * 2, 1)
