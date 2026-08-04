import logging
import re
import threading
from typing import Any, cast

from pydase.data_service.data_service_observer import DataServiceObserver
from pydase.utils.serialization.serializer import (
    dump,
    get_data_paths_from_serialized_object,
    get_nested_dict_by_path,
)
from pydase.utils.serialization.types import SerializedObject

from icon.server.data_access.db_context.influxdb.influxdb_v1 import DatabaseValueType
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


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
    # Check isinstance first: it is cheap, while dump() can be expensive for large
    # values (e.g. arrays streamed by a device).
    return not isinstance(new_value, DatabaseValueType) or (
        dump(new_value)["type"] != cached_value_dict["type"]
    )


_last_scannable_params: dict[str, list[str]] = {}
"""Last emitted scannable parameter lists keyed by device name.

Devices streaming non-scalar values (lists, arrays) pass the structure-change check
on every single update. Caching the previous result lets us skip the `device.update`
broadcast unless the scannable parameters actually changed, which otherwise floods
every connected client and freezes the UI.
"""

_DEBOUNCE_SECONDS = 0.5
"""Quiet period before recomputing scannable parameters after a structure change.

Some devices (e.g. Fastino) rebuild whole public lists on every parameter write:
a single update produces a burst of dozens of structural changes, and the scannable
parameters transiently change while the list is cleared and refilled. Debouncing
avoids walking the device tree and emitting transient parameter lists for every
event in the burst; only the settled state is compared and emitted.
"""

_pending_recompute_timers: dict[str, threading.Timer] = {}
_timer_lock = threading.Lock()


def _recompute_and_emit(observer: DataServiceObserver, device_name: str) -> None:
    with _timer_lock:
        _pending_recompute_timers.pop(device_name, None)

    device_proxies: dict[str, SerializedObject] = cast(
        "Any", observer.state_manager.cache_value
    )["devices"]["value"]["device_proxies"]["value"]

    try:
        scannable_params = get_scannable_params_list(device_proxies[device_name])
    except KeyError:
        # Device was removed/disabled in the meantime.
        _last_scannable_params.pop(device_name, None)
        return
    except Exception:
        logger.exception(
            "Failed recomputing scannable parameters for device %r", device_name
        )
        return

    if _last_scannable_params.get(device_name) == scannable_params:
        return
    _last_scannable_params[device_name] = scannable_params

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


def emit_scannable_device_params_change(
    observer: DataServiceObserver,
    full_access_path: str,
    value: Any,
    cached_value_dict: SerializedObject,
) -> None:
    device_name = get_device_name(full_access_path)

    if device_name is None or not device_structure_changed(value, cached_value_dict):
        return

    with _timer_lock:
        if device_name in _pending_recompute_timers:
            # A recompute is already scheduled; it reads the current cache when it
            # fires, so later changes in this burst are picked up automatically.
            return
        timer = threading.Timer(
            _DEBOUNCE_SECONDS, _recompute_and_emit, args=(observer, device_name)
        )
        timer.daemon = True
        _pending_recompute_timers[device_name] = timer
        timer.start()
