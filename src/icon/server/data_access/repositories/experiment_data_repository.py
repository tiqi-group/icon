import json
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
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


@dataclass
class DeviceSnapshot:
    """Full state of a connected device at the time of a measurement."""

    name: str
    """Device name (as registered in the devices table)."""
    url: str
    """pydase service URL of the device."""
    timestamp: str
    """Snapshot timestamp (ISO string)."""
    state: dict[str, Any] | None
    """Raw pydase ``SerializedObject`` tree for the device, or None if unreachable."""
    error: str | None = None
    """Error message if the device state could not be fetched."""


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
    job_id: int,
) -> None:
    """Write per-shot data into datasets under the 'shot_channels' group.

    Args:
        h5file: Open HDF5 file handle.
        data_point_index: Index of the current data point.
        shot_channels: Mapping of channel to per-shot integers.
        number_of_data_points: Current total number of stored data points.
        number_of_shots: Expected number of shots per channel.
        job_id: Job identifier, used for logging on a mismatched channel.
    """
    shot_group = h5file.require_group("shot_channels")
    for key, value in shot_channels.items():
        if len(value) != number_of_shots:
            logger.error(
                "Shot channel %r has %d values, expected %d (job %d); skipping.",
                key,
                len(value),
                number_of_shots,
                job_id,
            )
            continue

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
    if not stripped.startswith(("{", "[")):
        return None
    try:
        parsed = json.loads(stripped)
    except ValueError:
        return None
    return parsed


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


def _leaf_value(node: dict[str, Any]) -> Any:
    """Human-readable scalar for a pydase ``SerializedObject`` leaf node, None kept as None.

    Used both by `_serialized_leaf_value` (for writing) and by the flatten
    functions below (for diffing snapshots), which need to compare `None` against
    `None` rather than against an `h5py.Empty` sentinel.
    """
    node_type = node.get("type")
    value = node.get("value")
    if node_type == "Quantity" and isinstance(value, dict):
        return f"{value.get('magnitude')} {value.get('unit')}"
    if node_type == "Exception":
        return f"ERROR: {value}"
    return value


def _serialized_leaf_value(node: dict[str, Any]) -> Any:
    """Return a human-readable scalar for a pydase ``SerializedObject`` leaf node.

    A real HDF5 null (``h5py.Empty``) is used for ``None`` rather than the string
    "None", so a null value can't be confused with a device field whose actual
    string value is "None".
    """
    value = _leaf_value(node)
    return h5py.Empty("f") if value is None else value


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
            group, name, [h5py.Empty("f") if item is None else item for item in value]
        ):
            return
        list_group = group.require_group(name)
        for index, item in enumerate(value):
            _write_json_value(list_group, str(index), item)
    else:
        group.attrs[name] = h5py.Empty("f") if value is None else value


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


def _join_path(prefix: str, name: str) -> str:
    return f"{prefix}/{name}" if prefix else name


def _flatten_serialized_list(
    prefix: str, key: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Mirror of `_write_serialized_list`, producing ``{path: value}`` for diffing."""
    name = _sanitize_hdf5_name(key)
    is_scalar_list = all(
        item.get("type") not in ("method", "Quantity", "Exception")
        and not isinstance(item.get("value"), (dict, list))
        and not _is_expandable_json_string(item.get("value"))
        for item in items
    )
    if is_scalar_list:
        return {_join_path(prefix, name): tuple(_leaf_value(item) for item in items)}

    result: dict[str, Any] = {}
    list_prefix = _join_path(prefix, name)
    for index, item in enumerate(items):
        result.update(_flatten_serialized_node(list_prefix, str(index), item))
    return result


def _flatten_json_value(prefix: str, key: str, value: Any) -> dict[str, Any]:
    """Mirror of `_write_json_value`, producing ``{path: value}`` for diffing."""
    path = _join_path(prefix, _sanitize_hdf5_name(key))
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for child_key, child_value in value.items():
            result.update(_flatten_json_value(path, str(child_key), child_value))
        return result
    if isinstance(value, list):
        is_scalar_list = all(not isinstance(item, (dict, list)) for item in value)
        if is_scalar_list:
            return {path: tuple(value)}
        result = {}
        for index, item in enumerate(value):
            result.update(_flatten_json_value(path, str(index), item))
        return result
    return {path: value}


def _flatten_serialized_string(prefix: str, key: str, value: str) -> dict[str, Any]:
    """Mirror of `_write_serialized_string`, producing ``{path: value}`` for diffing."""
    parsed = _try_parse_json_container(value)
    if parsed is not None:
        return _flatten_json_value(prefix, key, parsed)
    return {_join_path(prefix, _sanitize_hdf5_name(key)): value}


def _flatten_serialized_node(
    prefix: str, key: str, node: dict[str, Any]
) -> dict[str, Any]:
    """Mirror of `_write_serialized_node`, producing ``{path: value}`` for diffing.

    Paths use the same segments `_write_serialized_node` would turn into HDF5
    groups/attributes, so two snapshots of the same device can be diffed leaf by
    leaf without touching the file.
    """
    if node.get("type") == "method":
        return {}
    name = _sanitize_hdf5_name(key)
    if node.get("type") in ("Quantity", "Exception"):
        return {_join_path(prefix, name): _leaf_value(node)}

    value = node.get("value")
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        child_prefix = _join_path(prefix, name)
        for child_key, child_node in value.items():
            result.update(_flatten_serialized_node(child_prefix, child_key, child_node))
        return result
    if isinstance(value, list):
        return _flatten_serialized_list(prefix, key, value)
    if node.get("type") == "str" and isinstance(value, str):
        return _flatten_serialized_string(prefix, key, value)
    return {_join_path(prefix, name): _leaf_value(node)}


def flatten_device_state(state: dict[str, Any]) -> dict[str, Any]:
    """Flatten a device's pydase state tree into ``{leaf_path: value}``.

    Mirrors `write_device_state_to_group`'s grouping so identical input produces
    identical keys, letting successive snapshots of the same device be diffed leaf
    by leaf instead of rewriting the whole tree on every call.
    """
    result: dict[str, Any] = {}
    for key, child_node in cast("dict[str, Any]", state.get("value") or {}).items():
        result.update(_flatten_serialized_node("", key, child_node))
    return result


def _write_leaf_value(parameters_group: h5py.Group, path: str, value: Any) -> None:
    """Write one leaf's current value into the browsable parameter tree at `path`."""
    group_path, _, attr_name = path.rpartition("/")
    group = (
        parameters_group.require_group(group_path) if group_path else parameters_group
    )
    if isinstance(value, tuple):
        _write_scalar_list_attr(
            group, attr_name, [h5py.Empty("f") if v is None else v for v in value]
        )
    else:
        group.attrs[attr_name] = h5py.Empty("f") if value is None else value


def _append_leaf_history(
    history_group: h5py.Group, path: str, timestamp: str, value: Any
) -> None:
    """Append one (timestamp, value) row to a leaf's growable history dataset.

    Scoped to scalar values -- a list-valued leaf is updated in place in the
    parameter tree instead (see `_write_leaf_value`), since tracking the history
    of a whole vector needs a different, ragged-array schema. A leaf becoming or
    leaving `None` is likewise reflected only in the live tree, not in history,
    since HDF5 has no per-row null for a fixed-dtype compound dataset.
    """
    if isinstance(value, tuple) or value is None:
        return

    dtype = [("timestamp", "S26"), ("value", get_hdf5_dtype(value))]
    if path in history_group:
        ds: h5py.Dataset = history_group[path]
        index = ds.shape[0]
        resize_dataset(ds, next_index=index, axis=0)
    else:
        ds = history_group.create_dataset(
            path, shape=(1,), maxshape=(None,), dtype=dtype
        )
        index = 0
    ds[index] = (timestamp.encode(), value)


def _write_device_snapshot_baseline(
    device_group: h5py.Group,
    history_group: h5py.Group,
    snapshot: DeviceSnapshot,
    new_state: dict[str, Any],
) -> None:
    """Write a device's full state tree, seeding history with its starting values."""
    if "parameters" in device_group:
        del device_group["parameters"]
    parameters_group = device_group.create_group("parameters")
    write_device_state_to_group(
        parameters_group, cast("dict[str, Any]", snapshot.state)
    )
    for path, value in new_state.items():
        _append_leaf_history(history_group, path, snapshot.timestamp, value)


def _write_device_snapshot_diff(
    device_group: h5py.Group,
    history_group: h5py.Group,
    snapshot: DeviceSnapshot,
    old_state: dict[str, Any],
    new_state: dict[str, Any],
) -> None:
    """Update only the parameters that changed since `old_state`, plus their history."""
    parameters_group = device_group.require_group("parameters")
    for path, value in new_state.items():
        if path in old_state and old_state[path] == value:
            continue
        _write_leaf_value(parameters_group, path, value)
        _append_leaf_history(history_group, path, snapshot.timestamp, value)


def _write_device_snapshot(
    devices_group: h5py.Group,
    snapshot: DeviceSnapshot,
    old_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Write/update one device's snapshot; returns its new flattened state.

    On the first snapshot for this device (`old_state` is None), writes the full
    state tree. On later calls, diffs the fresh state against `old_state` leaf by
    leaf and only touches (tree + history) the parameters that actually changed.
    Returns None (leaving `old_state` untouched by the caller) if the device was
    unreachable.
    """
    device_group = devices_group.require_group(snapshot.name)
    device_group.attrs["url"] = snapshot.url
    device_group.attrs["timestamp"] = snapshot.timestamp
    if snapshot.error is not None:
        device_group.attrs["error"] = snapshot.error
    elif "error" in device_group.attrs:
        del device_group.attrs["error"]

    if snapshot.state is None:
        return None

    new_state = flatten_device_state(snapshot.state)
    history_group = device_group.require_group("parameter_history")

    if old_state is None:
        _write_device_snapshot_baseline(
            device_group, history_group, snapshot, new_state
        )
    else:
        _write_device_snapshot_diff(
            device_group, history_group, snapshot, old_state, new_state
        )

    return new_state


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

        with h5_open(h5_path, "a") as h5file:
            write_experiment_data_point(h5file, data_point, job_id)
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
        previous_states: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Write/update the state of the connected devices under the 'devices' group.

        The first snapshot of a device (its name absent from `previous_states`)
        writes its full state tree under 'devices/<name>/parameters', mirrored as
        nested HDF5 groups/attributes (not a JSON blob) so it's browsable
        field-by-field in any HDF5 viewer. Every subsequent snapshot for a device
        already in `previous_states` is diffed against it leaf by leaf: only the
        parameters that actually changed are updated in the tree, and a
        (timestamp, value) row is appended for each to a growable dataset under
        'devices/<name>/parameter_history/<path>' -- so this can be called once per
        data point (to catch e.g. side effects on other parameters when a scanned
        one is set) without re-writing, or re-flooding the file with, the entire
        device state every time.

        Args:
            job_id: Job identifier.
            snapshots: Device snapshots to persist.
            previous_states: `{device_name: flattened_state}` as returned by the
                previous call for this job (empty on the first call).

        Returns:
            The updated `{device_name: flattened_state}` map. Pass this back in as
            `previous_states` on the next call for the same job.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename
        updated_states = dict(previous_states)

        with h5_open(h5_path, "a") as h5file:
            devices_group = h5file.require_group("devices")
            for snapshot in snapshots:
                new_state = _write_device_snapshot(
                    devices_group, snapshot, previous_states.get(snapshot.name)
                )
                if new_state is not None:
                    updated_states[snapshot.name] = new_state

            logger.debug("Wrote %d device snapshots for job %d", len(snapshots), job_id)

        return updated_states

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
        include_hardware_instructions: bool = False,
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
            include_hardware_instructions: If True, load ``hardware_instructions`` entries
                into ``hardware_instructions``.  Defaults to False — those blobs are
                large (~27 KB each, one per changed point) and are omitted
                from the default RPC response.

        Returns:
            Experiment data payload suitable for the API.
        """
        filename = get_filename_by_job_id(job_id)
        h5_path = Path(get_config().data.results_dir) / filename

        if not Path(h5_path).exists():
            logger.warning("The file %s does not exist.", h5_path)
            return ExperimentData()

        with h5_open(h5_path, "r") as h5file:
            return load_experiment_data(
                h5file,
                max_transfer_bytes,
                include_hardware_instructions=include_hardware_instructions,
            )


def prepare_readout_metadata(
    h5file: h5py.File,
    *,
    job_id: int,
    experiment_id: int,
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
    h5file: h5py.File, data_point: ExperimentDataPoint, job_id: int
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
        job_id=job_id,
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
    max_transfer_bytes: int = 50_000_000,
    *,
    include_hardware_instructions: bool = False,
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
        include_hardware_instructions: Wether to include hardware instructions
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
        shot_channels_group,
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
        data.readouts.shot_channels = {
            key: dict(enumerate(value[start_index:].tolist(), start=start_index))  # type: ignore
            for key, value in cast(
                "Sequence[tuple[str, h5py.Dataset]]",
                shot_channels_group.items(),
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
    h5file: h5py.File, result_channels: list[str], number_of_data_points: int = 1
) -> h5py.Dataset:
    sorted_result_channels = sorted(result_channels)
    result_dtype = np.dtype([(key, np.float64) for key in sorted_result_channels])

    return h5file.require_dataset(
        "result_channels",
        shape=(number_of_data_points,),
        maxshape=(None,),
        chunks=True,
        dtype=result_dtype,
        compression="gzip",
        compression_opts=9,
    )


POLL_INTERVAL = 0.05

_HDF5_GLOBAL_LOCK = threading.RLock()


@contextmanager
def h5_open(path: Path, mode: str, **kwargs: Any) -> Iterator[h5py.File]:
    with _HDF5_GLOBAL_LOCK:
        while True:
            try:
                with h5py.File(str(path), mode, **kwargs) as h5file:
                    yield h5file
                break
            except (OSError, FileNotFoundError):
                time.sleep(POLL_INTERVAL)


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
    with h5_open(h5_path, "a") as h5file:
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

    with h5_open(h5_path, "r") as h5file:
        return _read_fits_from_hdf5(h5file)


def delete_fit_result_by_job_id(*, job_id: int, result_channel: str) -> None:
    """Delete a fit result for a specific channel from the HDF5 file.

    Args:
        job_id: Job identifier.
        result_channel: Name of the result channel whose fit to delete.
    """
    filename = get_filename_by_job_id(job_id)
    h5_path = Path(get_config().data.results_dir) / filename
    with h5_open(h5_path, "a") as h5file:
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

    # Add vector channel size (average across all data points)
    total_vector_bytes = sum(
        dataset.shape[0] * dataset.dtype.itemsize
        for channel_group in (vector_channels_group or {}).values()
        for dataset in cast("h5py.Group", channel_group).values()
    )
    if total > 0:
        bytes_per_point += total_vector_bytes // total
    # JSON serialisation roughly doubles the raw size
    return max(bytes_per_point * 2, 1)
