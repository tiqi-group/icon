import errno
import itertools
import json
import logging
import threading
import time
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict, cast

import h5py  # type: ignore
import numpy as np
import numpy.typing as npt
from sqlalchemy.exc import NoResultFound

from icon.config.config import get_config
from icon.server.data_access.experiment_data import (
    DatabaseValueType,
    DeviceSnapshot,
    ExperimentData,
    ExperimentDataPoint,
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

logger = logging.getLogger(__name__)

MOST_RECENT_JOB_RUNS = 10
"""How many of the newest job runs to search when no job is specified."""

DEFAULT_MAX_TRANSFER_BYTES = 4_000_000
"""Approximate cap on the serialised payload of one data request."""


class _Hdf5DatasetCommonParams(TypedDict):
    """Common parameters for HDF5 Datasets."""

    compression: str
    compression_opts: int


_common_hdf5_dataset_params: _Hdf5DatasetCommonParams = {
    "compression": "gzip",
    "compression_opts": 4,
}


class HDF5FileMode(StrEnum):
    """HDF5 File modes - see https://docs.h5py.org/en/stable/high/file.html#opening-creating-files."""

    READ_ONLY = "r"
    """Read-only, file must exist (default)"""
    READ_WRITE_OR_FAIL = "r+"
    """Read/write, fail if not exists"""
    READ_WRITE_OR_CREATE = "a"
    """Read/write if exists, create otherwise"""
    CREATE_OR_FAIL = "w-"
    """Create file, fail if exists"""
    CREATE_OR_TRUNCATE = "w"
    """Create file, truncate if exists"""


class OSFileLockError(OSError):
    """Raised when an HDF5 file is locked by another process."""


_H5_FILE_OPEN_POLL_INTERVAL = 0.05
"""Initial wait between attempts to open a locked HDF5 file."""

_H5_FILE_OPEN_MAX_POLL_INTERVAL = 0.5
"""Cap on the exponential backoff between HDF5 file open attempts."""

_file_locks: dict[str, threading.RLock] = {}
"""Holding one process-wide lock for each result file, forcing sequential reads per file per process."""


def _result_filename(scheduled_time: datetime) -> str:
    """Return the HDF5 filename for a run scheduled at `scheduled_time`."""
    return f"{scheduled_time}.h5"


def get_filename_by_job_id(job_id: int) -> str:
    """Return the HDF5 filename for a job.

    Args:
        job_id: Job identifier.

    Returns:
        Filename derived from the job's scheduled time (e.g., "<iso>.h5").
    """
    return _result_filename(
        JobRunRepository.get_scheduled_time_by_job_id(job_id=job_id)
    )


def _recent_result_paths(results_dir: Path) -> list[Path]:
    """Return the newest result files, newest first."""
    return [
        results_dir / _result_filename(scheduled_time)
        for scheduled_time in JobRunRepository.get_recent_scheduled_times(
            limit=MOST_RECENT_JOB_RUNS
        )
    ]


def resize_dataset(dataset: h5py.Dataset, next_index: int, axis: int) -> None:
    """Resize a dataset to accommodate writing at a target index.

    Args:
        dataset: HDF5 dataset to resize.
        next_index: Index that must be writable.
        axis: Axis along which to grow.
    """
    dataset.resize(next_index + 1, axis)


def _parameter_value_unchanged(
    dataset: h5py.Dataset,
    value: str | float | bool,  # noqa: FBT001
) -> bool:
    """Return whether `value` equals the dataset's last stored entry."""
    if dataset.shape[0] == 0:
        return False
    last_value = dataset[-1]["value"]
    if isinstance(value, str):
        return last_value.decode() == value
    return last_value == value


def _make_parameter_dataset_extensible(
    parameters_group: h5py.Group, param_id: str
) -> h5py.Dataset:
    """Replace a fixed-size parameter dataset with an extensible copy.

    Parameter datasets are created contiguous to save space. On the
    rare event of a parameter update, it is copied into a new
    extensible dataset.

    Args:
        parameters_group: The file's ``parameters`` group.
        param_id: Name of the dataset to replace.

    Returns:
        The extensible dataset, holding the entries of the old one.
    """
    oldval = cast("h5py.Dataset", parameters_group[param_id])[:]
    del parameters_group[param_id]
    dataset = parameters_group.create_dataset(
        param_id,
        shape=(len(oldval) + 1,),
        maxshape=(None,),
        dtype=oldval.dtype,
    )
    dataset[: len(oldval)] = oldval
    return dataset


def write_hardware_instructions_to_dataset(
    h5file: h5py.File,
    data_point_index: int,
    hardware_instructions: str,
) -> None:
    """Append hardware instructions if it changed since the last entry.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        hardware_instructions: Serialized hardware instructions to append.
    """
    hw_instructions_dtype = [
        ("index", np.int32),
        ("Sequence", h5py.string_dtype()),
    ]
    hw_instructions_dataset = h5file.require_dataset(
        "hardware_instructions",
        shape=(0,),
        maxshape=(None,),
        chunks=True,
        dtype=hw_instructions_dtype,
        **_common_hdf5_dataset_params,
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
        **_common_hdf5_dataset_params,
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
            dtype=np.float64,
            chunks=True,
            **_common_hdf5_dataset_params,
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
        # Don't create a dataset for empty vector data.
        if str(data_point_index) not in channel_group and vector:
            channel_group.create_dataset(
                str(data_point_index),
                data=vector,
                **_common_hdf5_dataset_params,
            )


_MAX_ATTR_LIST_LEN = 1000
"""Above this length, a list of scalars is written as a dataset instead of an
attribute, since HDF5 attributes aren't meant to hold large payloads."""


def _sanitize_hdf5_name(name: str) -> str:
    """Replace '/', which HDF5 treats as a path separator, in group/attr names."""
    return name.replace("/", "_")


def _try_parse_json_container(text: str) -> dict[str, Any] | list[Any] | None:
    """Parse `text` as JSON if -- and only if -- it decodes to a dict or list.

    Some device plugins expose composite state as one JSON-encoded string field
    (rather than modeling it as nested pydase properties). Detecting that lets
    such fields be expanded into the same browsable group/attribute structure
    as native nested fields, instead of sitting there as opaque text.
    """
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return None
    try:
        parsed = json.loads(stripped)
    except ValueError:
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _is_expandable_json_string(value: Any) -> bool:
    return isinstance(value, str) and _try_parse_json_container(value) is not None


def _write_scalar_list_attr(group: h5py.Group, name: str, values: list[Any]) -> bool:
    """Try writing `values` as one attribute (or dataset, if large). True on success."""
    try:
        if len(values) > _MAX_ATTR_LIST_LEN:
            if name in group:
                del group[name]
            group.create_dataset(name, data=values)
        else:
            group.attrs[name] = values
    except (TypeError, ValueError):
        logger.debug("Could not write %r as a single attribute/dataset", name)
        return False
    return True


def _serialized_leaf_value(node: dict[str, Any]) -> Any:
    """Return a human-readable scalar for a pydase ``SerializedObject`` leaf node."""
    node_type = node.get("type")
    value = node.get("value")
    if node_type == "Quantity" and isinstance(value, dict):
        return f"{value.get('magnitude')} {value.get('unit')}"
    if node_type == "Exception":
        return f"ERROR: {value}"
    if value is None:
        return "None"
    return value


def _write_serialized_list(
    group: h5py.Group, key: str, items: list[dict[str, Any]]
) -> None:
    """Write a pydase 'list' node: as one attribute if all elements are scalar."""
    name = _sanitize_hdf5_name(key)
    is_scalar_list = all(
        item.get("type") not in ("method", "Quantity", "Exception")
        and not isinstance(item.get("value"), (dict, list))
        and not _is_expandable_json_string(item.get("value"))
        for item in items
    )
    if is_scalar_list:
        values = [_serialized_leaf_value(item) for item in items]
        if _write_scalar_list_attr(group, name, values):
            return

    list_group = group.require_group(name)
    for index, item in enumerate(items):
        _write_serialized_node(list_group, str(index), item)


def _write_json_value(group: h5py.Group, key: str, value: Any) -> None:
    """Mirror a plain (non-pydase) JSON-shaped value into HDF5 groups/attrs.

    Used to expand a device field whose value is a JSON-encoded string, once
    decoded -- the raw dict/list has no pydase 'type'/'value' wrapping, unlike
    ``_write_serialized_node``'s input.
    """
    name = _sanitize_hdf5_name(key)
    if isinstance(value, dict):
        child_group = group.require_group(name)
        for child_key, child_value in value.items():
            _write_json_value(child_group, str(child_key), child_value)
    elif isinstance(value, list):
        is_scalar_list = all(not isinstance(item, (dict, list)) for item in value)
        if is_scalar_list and _write_scalar_list_attr(
            group, name, ["None" if item is None else item for item in value]
        ):
            return
        list_group = group.require_group(name)
        for index, item in enumerate(value):
            _write_json_value(list_group, str(index), item)
    else:
        group.attrs[name] = "None" if value is None else value


def _write_serialized_string(group: h5py.Group, key: str, value: str) -> None:
    """Write a string leaf, expanding it first if it's itself JSON-encoded."""
    parsed = _try_parse_json_container(value)
    if parsed is not None:
        _write_json_value(group, key, parsed)
    else:
        group.attrs[_sanitize_hdf5_name(key)] = value


def _write_serialized_node(group: h5py.Group, key: str, node: dict[str, Any]) -> None:
    """Recursively mirror one pydase ``SerializedObject`` node into HDF5.

    Container nodes (a device, a sub-component, a plain dict) become nested
    HDF5 groups; scalar leaves (numbers, strings, enums, quantities, ...) become
    attributes on their parent group, so the result is browsable field-by-field
    in any HDF5 viewer. Methods are skipped -- they're actions, not state. A
    string leaf that is itself JSON-encoded (e.g. a config blob some device
    plugins report as one field) is expanded the same way instead of being left
    as opaque text.
    """
    if node.get("type") == "method":
        return
    if node.get("type") in ("Quantity", "Exception"):
        group.attrs[_sanitize_hdf5_name(key)] = _serialized_leaf_value(node)
        return

    value = node.get("value")
    if isinstance(value, dict):
        child_group = group.require_group(_sanitize_hdf5_name(key))
        for child_key, child_node in value.items():
            _write_serialized_node(child_group, child_key, child_node)
    elif isinstance(value, list):
        _write_serialized_list(group, key, value)
    elif node.get("type") == "str" and isinstance(value, str):
        _write_serialized_string(group, key, value)
    else:
        group.attrs[_sanitize_hdf5_name(key)] = _serialized_leaf_value(node)


def write_device_state_to_group(group: h5py.Group, state: dict[str, Any]) -> None:
    """Write a device's full pydase state tree into an HDF5 group, human-readably.

    Args:
        group: HDF5 group to populate (its existing content is not cleared).
        state: Root ``SerializedObject`` for the device, as returned by pydase's
            ``service_serialization`` event.
    """
    for key, child_node in cast("dict[str, Any]", state.get("value") or {}).items():
        _write_serialized_node(group, key, child_node)


class ExperimentDataRepository:
    """Repository for HDF5-based experiment data.

    Manages HDF5 file creation and updates (metadata, results, parameters), with
    hdf5-level locking to support concurrent writers.

    Initialize the data container for a new job by calling :meth:`initialize_for_job_id`.
    Initialization is required before any read/write operation is triggered.
    """

    @staticmethod
    def initialize_for_job_id(*, job_id: int) -> None:
        """Create the file.

        Args:
            job_id: Job identifier.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename
        with h5_open(
            h5_path,
            HDF5FileMode.CREATE_OR_FAIL,
            fs_strategy="page",
            fs_persist=True,
            fs_page_size=65536,
        ):
            pass

    @staticmethod
    def update_metadata_by_job_id(
        *,
        job_id: int,
        number_of_shots: int,
        repetitions: int,
        readout_metadata: ReadoutMetadata,
        local_parameter_timestamp: datetime | None = None,
        parameters: list[ScanParameter] | None = None,
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
        h5_path = Path(get_config().data.results_dir) / filename
        job = JobRepository.get_job_by_id(job_id=job_id, load_experiment_source=True)

        with h5_open(h5_path, HDF5FileMode.READ_WRITE_OR_FAIL) as h5file:
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
            h5file.attrs["scan_mode"] = job.scan_mode.value

        metadata_key_remap = {
            "readout_channel_windows": "result_channels",
            "shot_channel_windows": "shot_channels",
            "vector_channel_windows": "vector_channels",
        }
        emit_queue.put(
            {
                "event": f"experiment_{job_id}_metadata",
                "data": {
                    "readout_metadata": {
                        metadata_key_remap[key]: val
                        for key, val in asdict(readout_metadata).items()
                        if key in metadata_key_remap
                    }
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

        Writes scan parameters, result/shot/vector channels, and hardware instructions.

        Args:
            job_id: Job identifier.
            data_point: Data point payload to append.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename

        with h5_open(h5_path, HDF5FileMode.READ_WRITE_OR_FAIL) as h5file:
            write_experiment_data_point(h5file, data_point)
        logger.debug("Appended data to %s", h5_path)

        emit_queue.put(
            {
                "event": f"experiment_{job_id}",
                "data": asdict(data_point),
            }
        )

    @staticmethod
    def write_device_snapshots_by_job_id(
        *,
        job_id: int,
        snapshots: list[DeviceSnapshot],
    ) -> None:
        """Write the state of the connected devices under the 'devices' group.

        Creates one subgroup per device, holding every field the device's pydase
        service exposes -- mirrored as nested HDF5 groups/attributes (not a JSON
        blob) so the state is browsable field-by-field in any HDF5 viewer. Repeated
        calls for the same device overwrite its snapshot.

        Args:
            job_id: Job identifier.
            snapshots: Device snapshots to persist.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename

        with h5_open(h5_path, HDF5FileMode.READ_WRITE_OR_CREATE) as h5file:
            devices_group = h5file.require_group("devices")
            for snapshot in snapshots:
                device_group = devices_group.require_group(snapshot.name)
                device_group.attrs["url"] = snapshot.url
                device_group.attrs["timestamp"] = snapshot.timestamp
                if snapshot.error is not None:
                    device_group.attrs["error"] = snapshot.error
                elif "error" in device_group.attrs:
                    del device_group.attrs["error"]
                if "parameters" in device_group:
                    del device_group["parameters"]
                if snapshot.state is not None:
                    parameters_group = device_group.create_group("parameters")
                    write_device_state_to_group(parameters_group, snapshot.state)
            logger.debug("Wrote %d device snapshots for job %d", len(snapshots), job_id)

    @staticmethod
    def write_parameter_update_by_job_id(
        *,
        job_id: int,
        timestamp: str,
        parameter_values: dict[str, str | int | float | bool],
    ) -> None:
        """Append parameter updates under the 'parameters' group.

        Appends only when the value changed from the last entry.

        Args:
            job_id: Job identifier.
            timestamp: ISO timestamp string.
            parameter_values: Mapping of parameter id to value.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename
        parameter_updates = {}
        with h5_open(h5_path, HDF5FileMode.READ_WRITE_OR_FAIL) as h5file:
            parameters_group = h5file.require_group("parameters")

            for param_id, value in parameter_values.items():
                dtype = [("timestamp", "S26"), ("value", get_hdf5_dtype(value))]

                if param_id in parameters_group:
                    ds = cast("h5py.Dataset", parameters_group[param_id])
                    if _parameter_value_unchanged(ds, value):
                        continue

                    index = ds.shape[0]
                    if ds.chunks is None:
                        # ds is fixed-size. Replace it with resizeable copy of itself.
                        ds = _make_parameter_dataset_extensible(
                            parameters_group, param_id
                        )
                    else:
                        resize_dataset(ds, next_index=index, axis=0)
                else:
                    # create fixed sized dataset which gets replaced with resizeable dataset on demand.
                    ds = parameters_group.create_dataset(
                        param_id,
                        shape=(1,),
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
        max_transfer_bytes: int = DEFAULT_MAX_TRANSFER_BYTES,
        include_hardware_instructions: bool = False,
        include_all_shots: bool = False,
    ) -> ExperimentData:
        """Load stored data for a job from its HDF5 file.

        When loading all data would exceed *max_transfer_bytes*, only the
        last N data points that fit within the budget are returned.  The
        budget is estimated from HDF5 metadata (channel count, shots per
        channel) without reading actual data.

        Args:
            job_id: Job identifier.
            max_transfer_bytes: Approximate cap on the serialised payload
                size in bytes.  Defaults to 4 MB.
            include_hardware_instructions: If True, load ``hardware_instructions`` entries
                into ``hardware_instructions``.  Defaults to False — those blobs are
                large (~27 KB each, one per changed point) and are omitted
                from the default RPC response.
            include_all_shots: If True, return the raw shots of every data point.
                Defaults to False, which returns only the newest data point's
                shots.

        Returns:
            Experiment data payload suitable for the API.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename

        if not Path(h5_path).exists():
            logger.warning("The file %s does not exist.", h5_path)
            return ExperimentData()

        with h5_open(h5_path, HDF5FileMode.READ_ONLY) as h5file:
            return load_experiment_data(
                h5file,
                max_transfer_bytes,
                include_hardware_instructions=include_hardware_instructions,
                include_all_shots=include_all_shots,
            )

    @staticmethod
    def get_hardware_instructions(
        *,
        job_id: int | None = None,
        index: int | None = None,
    ) -> str | None:
        """Return stored hardware instructions (the serialized sequence JSON).

        Args:
            job_id: Job to read from. Defaults to the most recent job with
                stored hardware instructions, looking no further back than the
                ``MOST_RECENT_JOB_RUNS`` most recent runs.
            index: Data point index within the job. Defaults to the last stored
                entry. Instructions are stored deduplicated (one entry per
                change), so the entry active at *index* is returned.

        Returns:
            The serialized hardware instructions, or None when nothing is
            stored for the requested scope.
        """
        results_dir = Path(get_config().data.results_dir)
        if job_id is not None:
            try:
                paths = [results_dir / get_filename_by_job_id(job_id)]
            except NoResultFound:
                return None
        else:
            paths = _recent_result_paths(results_dir)

        for path in paths:
            if not path.is_file():
                continue
            instructions = _read_hardware_instructions(path, index=index)
            if instructions is not None:
                return instructions
        return None


def _read_hardware_instructions(path: Path, *, index: int | None) -> str | None:
    """Read the instructions entry active at *index* (last entry if None).

    Only the requested entry is read: the stored blobs are tens of kilobytes
    each and a scan stores one per change, so reading the whole dataset to
    return a single sequence would transfer megabytes.
    """
    with h5_open(path, HDF5FileMode.READ_ONLY) as h5file:
        dataset = h5file.get("hardware_instructions")
        if not isinstance(dataset, h5py.Dataset) or dataset.shape[0] == 0:
            return None

        entry_index = dataset.shape[0] - 1
        if index is not None:
            # The entry active at *index* is the last one stored at or before
            # it. Scanning rather than bisecting keeps that true even if
            # entries are ever stored out of order, as re-taking a data point
            # would do.
            change_indices = cast("npt.NDArray[np.int32]", dataset.fields("index")[:])
            positions = np.flatnonzero(change_indices <= index)
            if positions.size == 0:
                return None
            entry_index = int(positions[-1])

        return cast("bytes", dataset[entry_index]["Sequence"]).decode()


def prepare_readout_metadata(
    h5file: h5py.File,
    *,
    job_id: int,
    experiment_id: str,
    number_of_shots: int,
    repetitions: int,
    readout_metadata: ReadoutMetadata,
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
        dtype=scan_parameter_dtype,
        chunks=True,
        **_common_hdf5_dataset_params,
    )

    for parameter in parameters:
        if parameter.device is not None:
            h5file["scan_parameters"].attrs[parameter.unique_id()] = (
                f"name={parameter.device.name} url={parameter.device.url}"
                f"description={parameter.device.description}"
            )

    if readout_metadata.readout_channel_names:
        result_dataset = get_result_channels_dataset(
            h5file=h5file,
            result_channels=readout_metadata.readout_channel_names,
        )
        result_dataset.attrs["Plot window metadata"] = json.dumps(
            [asdict(w) for w in readout_metadata.readout_channel_windows]
        )

    shot_group = h5file.require_group("shot_channels")
    shot_group.attrs["Plot window metadata"] = json.dumps(
        [asdict(w) for w in readout_metadata.shot_channel_windows]
    )

    vector_group = h5file.require_group("vector_channels")
    vector_group.attrs["Plot window metadata"] = json.dumps(
        [asdict(w) for w in readout_metadata.vector_channel_windows]
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
    write_results_to_dataset(
        h5file=h5file,
        data_point_index=data_point.index,
        result_channels=data_point.readouts.result_channels,
        number_of_data_points=number_of_data_points,
    )

    write_shot_channels_to_datasets(
        h5file=h5file,
        data_point_index=data_point.index,
        shot_channels=data_point.readouts.shot_channels,
        number_of_data_points=number_of_data_points,
        number_of_shots=number_of_shots,
    )

    write_vector_channels_to_datasets(
        h5file=h5file,
        data_point_index=data_point.index,
        vector_channels=data_point.readouts.vector_channels,
    )

    write_hardware_instructions_to_dataset(
        h5file=h5file,
        data_point_index=data_point.index,
        hardware_instructions=data_point.hardware_instructions,
    )

    if data_point.index >= number_of_data_points:
        h5file.attrs["number_of_data_points"] = data_point.index + 1


def load_experiment_data(
    h5file: h5py.File,
    max_transfer_bytes: int = DEFAULT_MAX_TRANSFER_BYTES,
    *,
    include_hardware_instructions: bool = False,
    include_all_shots: bool = False,
) -> ExperimentData:
    """Load stored data for a job from its HDF5 file.

    When loading all data would exceed *max_transfer_bytes*, only the
    last N data points that fit within the budget are returned.  The
    budget is estimated from HDF5 metadata (channel count, shots per
    channel) without reading actual data.

    Args:
        h5file: File to load from.
        max_transfer_bytes: Approximate cap on the serialised payload
            size in bytes.  Defaults to 4 MB.
        include_hardware_instructions: Whether to include hardware instructions.
        include_all_shots: If True, return the raw shots of every data point.
            Defaults to False, which returns only the newest data point's
            shots.

    Returns:
        Experiment data payload suitable for the API.
    """
    total = int(h5file.attrs.get("number_of_data_points", 0))
    data = ExperimentData(
        realtime_scan=bool(h5file.attrs.get("realtime_scan", False)),
        total_data_points=total,
    )
    shot_channels_group: h5py.Group | None = h5file.get("shot_channels")
    result_channel_dataset = h5file.get("result_channels")
    scan_parameters: h5py.Dataset | None = h5file.get("scan_parameters")
    vector_channels_group: h5py.Group | None = h5file.get("vector_channels")

    # Estimate bytes per data point from HDF5 metadata
    bytes_per_point = estimate_bytes_per_data_point(
        total,
        shot_channels_group if include_all_shots else None,
        result_channel_dataset,
        vector_channels_group,
        scan_parameters,
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

    if result_channel_dataset is not None:
        plot_metadata: str | None = result_channel_dataset.attrs.get(
            "Plot window metadata"
        )
        data.plot_windows.result_channels = [
            PlotWindowMetadata(**d)
            for d in (json.loads(plot_metadata) if plot_metadata else [])
        ]
        result_channels = cast("npt.NDArray[Any]", result_channel_dataset[start_index:])  # type: ignore
        data.readouts.result_channels = {
            channel_name: dict(
                enumerate(
                    cast("list[float]", result_channels[channel_name].tolist()),
                    start=start_index,
                )
            )
            for channel_name in cast("tuple[str, ...]", result_channels.dtype.names)
        }

    # Convert shot channels into dicts with index as key
    if shot_channels_group is not None:
        plot_metadata = shot_channels_group.attrs.get("Plot window metadata")
        data.plot_windows.shot_channels = [
            PlotWindowMetadata(**d)
            for d in (json.loads(plot_metadata) if plot_metadata else [])
        ]
        shot_start_index = (
            start_index if include_all_shots else max(start_index, total - 1)
        )
        data.readouts.shot_channels = {
            key: dict(
                enumerate(  # type: ignore[call-overload]
                    value[shot_start_index:].tolist(), start=shot_start_index
                )
            )
            for key, value in cast(
                "Sequence[tuple[str, h5py.Dataset]]", shot_channels_group.items()
            )
        }

    if vector_channels_group is not None:
        plot_metadata = vector_channels_group.attrs.get("Plot window metadata")
        data.plot_windows.vector_channels = [
            PlotWindowMetadata(**d)
            for d in (json.loads(plot_metadata) if plot_metadata else [])
        ]
        data.readouts.vector_channels = {
            channel_name: {
                int(name): cast("h5py.Dataset", vector_group[name])[:].tolist()
                for name in vector_group
                if int(name) >= start_index
            }
            for channel_name, vector_group in cast(
                "Sequence[tuple[str, h5py.Group]]",
                vector_channels_group.items(),
            )
        }

    if include_hardware_instructions:
        data.hardware_instructions = [
            (
                cast("np.int32", entry["index"]).item(),
                entry["Sequence"].decode(),
            )
            for entry in cast(
                "h5py.Dataset | tuple[()]", h5file.get("hardware_instructions", ())
            )
        ]
    data.parameters = extract_parameter_values(h5file)
    data.fits = _read_fits_from_hdf5(h5file)
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
    h5file: h5py.File, result_channels: list[str], number_of_data_points: int = 0
) -> h5py.Dataset:
    """Return the 'result_channels' dataset, creating it if it does not exist yet."""
    sorted_result_channels = sorted(result_channels)
    result_dtype = np.dtype([(key, np.float64) for key in sorted_result_channels])

    return h5file.require_dataset(
        "result_channels",
        shape=(number_of_data_points,),
        maxshape=(None,),
        dtype=result_dtype,
        chunks=True,
        **_common_hdf5_dataset_params,
    )


@contextmanager
def _in_process_lock(path: Path, timeout: float) -> Generator[None]:
    """Acquire the process-wide lock guarding `path`.

    The lock is required because libhdf5 produces a segfault under certain
    sequences of operations on the same file from within one process,
    see https://github.com/h5py/h5py/issues/2920.

    Args:
        path: Path of the HDF5 file to guard.
        timeout: Seconds to wait for the lock.

    Raises:
        TimeoutError: The lock was not acquired within `timeout`.
    """
    lock = _file_locks.setdefault(str(path.resolve()), threading.RLock())
    if not lock.acquire(timeout=timeout):
        raise TimeoutError(
            f"Timed out after {timeout} s waiting for in-process access to {path}."
        )
    try:
        yield
    finally:
        lock.release()


def _h5_open_with_retry(
    path: Path, mode: HDF5FileMode, *, deadline: float, **kwargs: Any
) -> h5py.File:
    """Open `path`, retrying while another process holds the OS file lock.

    Args:
        path: Path to the HDF5 file.
        mode: Passed to `h5py.File`.
        deadline: Bounds the wait to an absolute time (monotonic) in seconds.
        kwargs: Passed to `h5py.File`.

    Returns:
        The open `h5py.File`.

    Raises:
        TimeoutError: The OS file lock was still held at `deadline`.
        OSError: The file could not be opened for any other reason.
    """
    interval = _H5_FILE_OPEN_POLL_INTERVAL
    for attempt in itertools.count(1):
        try:
            h5file = _h5_open_once(path, mode, **kwargs)
            break
        except OSFileLockError as exc:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out waiting for the HDF5 file lock "
                    f"on {path} (mode {mode!r}, {attempt} attempts)."
                ) from exc
            logger.debug(
                "HDF5 file %s (mode=%s) is locked; retrying in %.2f s.",
                path,
                mode,
                min(interval, remaining),
            )
            time.sleep(min(interval, remaining))
            interval = min(interval * 2, _H5_FILE_OPEN_MAX_POLL_INTERVAL)

    if attempt > 1:
        logger.info(
            "Opened HDF5 file %s (mode=%s) after %d attempts.", path, mode, attempt
        )
    return h5file


def _is_file_lock_error(exc: OSError) -> bool:
    """Return whether `exc` is HDF5 failing to acquire the OS file lock."""
    if exc.errno in {errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK}:
        return True
    return exc.errno is None and "unable to lock file" in str(exc).lower()


def _h5_open_once(path: Path, mode: HDF5FileMode, **kwargs: Any) -> h5py.File:
    try:
        h5file = h5py.File(str(path), mode, **kwargs)
    except OSError as exc:
        if _is_file_lock_error(exc):
            raise OSFileLockError(
                f"HDF5 file {path} is locked by another process (mode {mode!r})."
            ) from exc
        raise
    return h5file


@contextmanager
def h5_open(
    path: Path, mode: HDF5FileMode, *, timeout: float | None = None, **kwargs: Any
) -> Generator[h5py.File]:
    """Open an HDF5 file under a process-wide per-file lock.

    Opens of the same file are serialised within this process by a per-file
    lock; different files proceed in parallel. The OS-native HDF5 lock may still
    be held by another process, in which case the open is retried with a capped
    backoff. Every other failure is permanent and raised immediately.

    Args:
        path: Path of the HDF5 file.
        mode: Mode passed to `h5py.File`.
        timeout: Seconds to wait in total, for the in-process lock and the file
            lock together. Defaults to `data.h5_open_timeout_seconds` from the
            configuration.
        kwargs: Additional arguments passed to `h5py.File`.

    Yields:
        The open `h5py.File`.

    Raises:
        TimeoutError: The file could not be opened within `timeout` due to locking.
        OSError: The file could not be opened for any other reason.
    """
    if timeout is None:
        timeout = get_config().data.h5_open_timeout_seconds
    deadline = time.monotonic() + timeout

    with (
        _in_process_lock(path, timeout=timeout),
        _h5_open_with_retry(path, mode, deadline=deadline, **kwargs) as h5file,
    ):
        yield h5file


def _read_fits_from_hdf5(
    h5file: h5py.File,
) -> dict[str, FitResult]:
    """Read all fit results from an HDF5 file."""
    if "fits" not in h5file:
        return {}

    fits: dict[str, FitResult] = {}
    fits_group = cast("h5py.Group", h5file["fits"])
    for channel_name in fits_group:
        channel_group = cast("h5py.Group", fits_group[channel_name])
        fit_data = json.loads(cast("str", channel_group.attrs["fit_result"]))
        fits[channel_name] = FitResult(**fit_data)
    return fits


def write_fit_result_by_job_id(
    *,
    job_id: int,
    fit_result: FitResult,
) -> None:
    """Write a fit result into the HDF5 file for a job.

    Creates or overwrites the ``fits/<result_channel>`` group.

    Args:
        job_id: Job identifier.
        fit_result: The fit result to persist.
    """
    filename = get_filename_by_job_id(job_id)
    h5_path = Path(get_config().data.results_dir) / filename
    with h5_open(h5_path, HDF5FileMode.READ_WRITE_OR_FAIL) as h5file:
        fits_group = h5file.require_group("fits")
        channel = fit_result.result_channel
        if channel in fits_group:
            del fits_group[channel]
        grp = fits_group.create_group(channel)
        grp.attrs["fit_result"] = json.dumps(asdict(fit_result))


def get_fit_results_by_job_id(*, job_id: int) -> dict[str, FitResult]:
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

    with h5_open(h5_path, HDF5FileMode.READ_ONLY) as h5file:
        return _read_fits_from_hdf5(h5file)


def delete_fit_result_by_job_id(*, job_id: int, result_channel: str) -> None:
    """Delete a fit result for a specific channel from the HDF5 file.

    Args:
        job_id: Job identifier.
        result_channel: Name of the result channel whose fit to delete.
    """
    filename = get_filename_by_job_id(job_id)
    h5_path = Path(get_config().data.results_dir) / filename
    with h5_open(h5_path, HDF5FileMode.READ_WRITE_OR_FAIL) as h5file:
        if "fits" in h5file and result_channel in h5file["fits"]:
            del h5file["fits"][result_channel]


def estimate_bytes_per_data_point(
    total: int,
    shot_channels_group: h5py.Group | None,
    result_channel_dataset: h5py.Group | None,
    vector_channels_group: h5py.Group | None,
    scan_parameters: h5py.Dataset | None,
) -> int:
    """Estimate bytes per data point from HDF5 metadata.

    Return total number of data points in `h5file` and estimated bytes per data point.
    """
    bytes_per_point = sum(
        ds.shape[1] * ds.dtype.itemsize for ds in (shot_channels_group or {}).values()
    ) + sum(
        ds.dtype.itemsize
        for ds in (result_channel_dataset, scan_parameters)
        if ds is not None
    )

    total_vector_bytes = 0
    for channel_group in (vector_channels_group or {}).values():
        vectors = cast("h5py.Group", channel_group)
        sample_name = next(iter(vectors), None)
        if sample_name is None:
            continue
        sample = cast("h5py.Dataset", vectors[sample_name])
        total_vector_bytes += sample.shape[0] * sample.dtype.itemsize * len(vectors)
    if total > 0:
        bytes_per_point += total_vector_bytes // total
    # JSON serialisation roughly doubles the raw size
    return max(bytes_per_point * 2, 1)
