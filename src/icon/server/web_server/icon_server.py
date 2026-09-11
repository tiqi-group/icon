import asyncio
import logging
import queue
import re
from typing import Any

import pydase
from pydase.utils.serialization.types import SerializedObject

from icon.server.utils.scannable_device_parameters import (
    emit_scannable_device_params_change,
    get_device_name,
)
from icon.server.web_server.sio_setup import device_updates_room
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)

_CONNECTED_PATH_PATTERN = re.compile(r'^devices\.device_proxies\["[^"]+"\]\.connected$')
"""Reachability paths which stay broadcast to all clients (rare and cheap)."""


def _install_device_room_emit(sio: Any) -> None:
    """Reroute pydase `notify` events to opt-in socket.io rooms.

    pydase `notify` events from device proxies are broadcast to all client by default.
    Re-route them to a device update broadcast room and device-specific update rooms,
    which clients can subscribe to.
    """
    original_emit = sio.emit

    async def emit_with_device_room(
        event: str, data: Any = None, **kwargs: Any
    ) -> None:
        if (
            event == "notify"
            and kwargs.get("room") is None
            and kwargs.get("to") is None
            and isinstance(data, dict)
        ):
            full_access_path = data.get("data", {}).get("full_access_path", "")
            device_name = get_device_name(full_access_path)
            if (
                full_access_path.startswith("devices.device_proxies")
                and device_name is not None
                and not _CONNECTED_PATH_PATTERN.match(full_access_path)
            ):
                kwargs["to"] = [
                    device_updates_room(),  # Device update broadcast room
                    device_updates_room(device_name),  # Device-specific update room
                ]
        return await original_emit(event, data=data, **kwargs)

    sio.emit = emit_with_device_room


class IconServer(pydase.Server):
    async def post_startup(self) -> None:
        sio = self._web_server._sio

        _install_device_room_emit(sio)

        async def emit_worker() -> None:
            while not self.should_exit:
                try:
                    emit_event = await asyncio.to_thread(emit_queue.get, timeout=1.0)
                except queue.Empty:
                    continue
                await sio.emit(
                    event=emit_event["event"],
                    data=emit_event.get("data", None),
                    room=emit_event.get("room", None),
                )

        asyncio.create_task(emit_worker())

        def devices_callback(
            full_access_path: str, value: Any, cached_value_dict: SerializedObject
        ) -> None:
            """This callback handles structural changes of devices.

            If the structure of
            a device changes, it will re-calculate the scannable parameters and emit
            them to the interested clients.
            """
            if full_access_path.startswith("devices.device_proxies"):
                emit_scannable_device_params_change(
                    self._observer, full_access_path, value, cached_value_dict
                )

        self._observer.add_notification_callback(devices_callback)
