import re
from typing import Any, cast

from pydase.data_service.data_service_observer import DataServiceObserver
from pydase.utils.serialization.serializer import (
    dump,
    get_data_paths_from_serialized_object,
    get_nested_dict_by_path,
)
from pydase.utils.serialization.types import SerializedObject

from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.web_server.socketio_emit_queue import emit_queue


def is_scannable_parameter(serialized_object: SerializedObject) -> bool:
    """Is this serialized object scannable through icon?"""

    return serialized_object["type"] in ("float", "int", "Quantity")


def get_scannable_params_list(
    serialized_object: SerializedObject, prefix: str = ""
) -> list[str]:
    """Get a list of full access paths of scannable parameters."""

    scannable_params: list[str] = []
    for path in get_data_paths_from_serialized_object(serialized_object):
        nested_dict = get_nested_dict_by_path(
            cast("dict[str, SerializedObject]", serialized_object["value"]), path
        )
        if is_scannable_parameter(nested_dict):
            scannable_params.append(prefix + nested_dict["full_access_path"])
    return scannable_params


def get_device_name(full_access_path: str) -> str | None:
    """Extracts the device name from the full access path.

    Args:
        full_access_path: Full access path of the attribute.

    Returns:
        The device name.

    Example:
        ```python
        >>> get_device_name('devices.device_proxies["My device name"]')
        My device name
        ```
    """

    match = re.match(r'devices\.device_proxies\["([^"]+)"\]', full_access_path)
    if match is None:
        return None

    return match.group(1)


def device_structure_changed(
    new_value: Any, cached_value_dict: SerializedObject
) -> bool:
    return dump(new_value)["type"] != cached_value_dict["type"] or not isinstance(
        new_value, DatabaseValueType
    )


def emit_scannable_device_params_change(
    observer: DataServiceObserver,
    full_access_path: str,
    value: Any,
    cached_value_dict: SerializedObject,
) -> None:
    device_name = get_device_name(full_access_path)

    if not device_structure_changed(value, cached_value_dict) or device_name is None:
        return

    scannable_params = get_scannable_params_list(
        observer.state_manager.cache_value["devices"]["value"]["device_proxies"][
            "value"
        ][device_name]
    )

    emit_queue.put(
        {
            "event": "device.update",
            "data": {
                "device_name": device_name,
                "updated_properties": {
                    "scannable_params": scannable_params,
                },
            },
        }
    )
