import logging
import sys
from types import TracebackType
from typing import TYPE_CHECKING, Any

import socketio  # type: ignore

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


class Client:
    def __init__(
        self,
        url: str,
    ):
        self._url = url
        self._sio = socketio.Client()
        self._sio.on("connect", self._handle_connect)
        self._sio.on("disconnect", self._handle_disconnect)

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

    def _handle_connect(self) -> None:
        logger.debug("Connected")

    def _handle_disconnect(self) -> None:
        logger.debug("Disconnected")

    def connect(self) -> None:
        if not self._sio.connected:
            self._sio.connect(
                self._url,
                socketio_path="/ws/socket.io",
                transports=["websocket"],
                retry=False,
            )

    def disconnect(self) -> None:
        if self._sio.connected:
            self._sio.disconnect()

    def get_value(self, full_access_path: str) -> Any:
        serialized_value: SerializedIconObject | None = self._sio.call(
            "get_value", full_access_path
        )
        if serialized_value is not None:
            return loads(serialized_value)
        return None

    def set_value(self, full_access_path: str, new_value: Any) -> Any:
        return self._sio.call(
            "update_value",
            {
                "access_path": full_access_path,
                "value": dump(new_value),
            },
        )

    def trigger_method(
        self,
        full_access_path: str,
        *,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] = {},
    ) -> Any:
        result = self._sio.call(
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
