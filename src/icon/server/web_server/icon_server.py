import asyncio
import logging
import queue
from typing import Any

import pydase
from pydase.utils.serialization.types import SerializedObject

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

        # Add notification callback to observer
        def devices_callback(
            full_access_path: str, value: Any, cached_value_dict: SerializedObject
        ) -> None:
            if cached_value_dict != {} and self._loop.is_running():
                if not full_access_path.startswith("devices._device_proxies"):
                    return
                logger.info(f"{full_access_path}: {value}")

                async def notify() -> None:
                    try:
                        await sio.emit(
                            "notify",
                            {
                                "data": {
                                    "full_access_path": full_access_path,
                                    "value": cached_value_dict,
                                }
                            },
                        )
                    except Exception as e:
                        logger.warning("Failed to send notification: %s", e)

                self._loop.create_task(notify())

        self._observer.add_notification_callback(devices_callback)
