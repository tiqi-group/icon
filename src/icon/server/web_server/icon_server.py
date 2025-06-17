import asyncio
import queue

import pydase

from icon.server.web_server.socketio_emit_queue import emit_queue


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
