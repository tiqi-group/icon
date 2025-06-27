import asyncio
import logging
import queue
from typing import Any

import pydase
from pydase.utils.serialization.types import SerializedObject

from icon.server.utils.scannable_device_parameters import (
    emit_scannable_device_params_change,
)
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


class IconServer(pydase.Server):
    async def post_startup(self) -> None:
        sio = self._web_server._sio

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
            """This callback handles structural changes of devices. If the structure of
            a device changes, it will re-calculate the scannable parameters and emit
            them to the interested clients."""

            if full_access_path.startswith("devices.device_proxies"):
                emit_scannable_device_params_change(
                    self._observer, full_access_path, value, cached_value_dict
                )

        self._observer.add_notification_callback(devices_callback)
