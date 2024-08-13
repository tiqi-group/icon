import asyncio
import logging
import sys
import threading
from types import TracebackType
from typing import TYPE_CHECKING, Any

import socketio  # type: ignore

from icon.client.api.scheduler_controller import SchedulerController
from icon.serialization.deserializer import loads
from icon.serialization.serializer import dump

if TYPE_CHECKING:
    from icon.serialization.types import SerializedIconObject

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def asyncio_loop_thread(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


class Client:
    def __init__(
        self,
        url: str,
    ):
        self._loop = asyncio.new_event_loop()
        self._url = url
        self._sio = socketio.AsyncClient()
        self._sio.on("connect", self._handle_connect)
        self._sio.on("disconnect", self._handle_disconnect)
        self._thread = threading.Thread(
            target=asyncio_loop_thread, args=(self._loop,), daemon=True
        )
        self._thread.start()
        self.scheduler = SchedulerController(self)

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __del__(self) -> None:
        self.disconnect()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.disconnect()

    async def _handle_connect(self) -> None:
        logger.debug("Connected")

    async def _handle_disconnect(self) -> None:
        logger.debug("Disconnected")

    async def _async_connect(self) -> None:
        if not self._sio.connected:
            await self._sio.connect(
                self._url,
                socketio_path="/ws/socket.io",
                transports=["websocket"],
                retry=False,
            )

    def connect(self) -> None:
        connection_future = asyncio.run_coroutine_threadsafe(
            self._async_connect(), self._loop
        )
        connection_future.result()

    def disconnect(self) -> None:
        connection_future = asyncio.run_coroutine_threadsafe(
            self._async_disconnect(), self._loop
        )
        connection_future.result()

    async def _async_disconnect(self) -> None:
        if self._sio.connected:
            await self._sio.disconnect()

    async def _async_get_value(self, full_access_path: str) -> Any:
        serialized_value: SerializedIconObject | None = await self._sio.call(
            "get_value", full_access_path
        )
        if serialized_value is not None:
            return loads(serialized_value)
        return None

    def get_value(self, full_access_path: str) -> Any:
        get_value_future = asyncio.run_coroutine_threadsafe(
            self._async_get_value(full_access_path), self._loop
        )
        return get_value_future.result()

    async def _async_set_value(self, full_access_path: str, new_value: Any) -> Any:
        return await self._sio.call(
            "update_value",
            {
                "access_path": full_access_path,
                "value": dump(new_value),
            },
        )

    def set_value(self, full_access_path: str, new_value: Any) -> Any:
        set_value_future = asyncio.run_coroutine_threadsafe(
            self._async_set_value(full_access_path, new_value), self._loop
        )
        return set_value_future.result()

    async def _async_trigger_method(
        self,
        full_access_path: str,
        *,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] = {},
    ) -> Any:
        result = await self._sio.call(
            "trigger_method",
            {
                "access_path": full_access_path,
                "args": dump(list(args)),
                "kwargs": dump(kwargs),
            },
        )

        if result is not None:
            return loads(serialized_object=result)

        return None

    def trigger_method(
        self,
        full_access_path: str,
        *,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] = {},
    ) -> Any:
        trigger_method_future = asyncio.run_coroutine_threadsafe(
            self._async_trigger_method(full_access_path, args=args, kwargs=kwargs),
            self._loop,
        )
        return trigger_method_future.result()
