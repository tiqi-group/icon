import asyncio
import logging
import queue
import re
from typing import Any

import pydase
from pydase.utils.serialization.types import SerializedObject

from icon.server.utils.scannable_device_parameters import (
    emit_scannable_device_params_change,
)
from icon.server.web_server.sio_setup import DEVICE_UPDATES_ROOM
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)

_CONNECTED_PATH_PATTERN = re.compile(r'^devices\.device_proxies\["[^"]+"\]\.connected$')
"""Reachability paths which stay broadcast to all clients (rare and cheap)."""


def _install_device_room_emit(sio: Any) -> None:
    """Reroute high-rate device proxy `notify` events to an opt-in room.

    pydase broadcasts every state change as a "notify" event to all connected
    clients. High-rate device proxy updates (chatty pydase devices) can flood
    every browser tab and freeze the UI. Reroute those to a room that the
    frontend only joins while the Devices page is open.
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
            if full_access_path.startswith(
                "devices.device_proxies"
            ) and not _CONNECTED_PATH_PATTERN.match(full_access_path):
                kwargs["room"] = DEVICE_UPDATES_ROOM
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
