import asyncio
import logging
from io import StringIO
from typing import TYPE_CHECKING, Any, TypedDict

import pandas as pd
import pydase
import pydase.client.proxy_loader
import socketio  # type: ignore[import-untyped]

from icon.client.api.scheduler_controller import SchedulerController
from icon.serialization.deserializer import loads
from icon.serialization.serializer import dump

if TYPE_CHECKING:
    from icon.serialization.types import SerializedIconObject

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ExperimentData(TypedDict):
    job_id: int
    data: str


def trigger_method(
    sio_client: socketio.AsyncClient,
    loop: asyncio.AbstractEventLoop,
    access_path: str,
    args: list[Any],
    kwargs: dict[str, Any],
) -> Any:
    async def async_trigger_method() -> Any:
        return await sio_client.call(
            "trigger_method",
            {
                "access_path": access_path,
                "args": dump(args),
                "kwargs": dump(kwargs),
            },
        )

    result: SerializedIconObject | None = asyncio.run_coroutine_threadsafe(
        async_trigger_method(),
        loop=loop,
    ).result()

    if result is not None:
        return loads(serialized_object=result)

    return None


def update_value(
    sio_client: socketio.AsyncClient,
    loop: asyncio.AbstractEventLoop,
    access_path: str,
    value: Any,
) -> Any:
    async def set_result() -> Any:
        return await sio_client.call(
            "update_value",
            {
                "access_path": access_path,
                "value": dump(value),
            },
        )

    result: SerializedIconObject | None = asyncio.run_coroutine_threadsafe(
        set_result(),
        loop=loop,
    ).result()

    if result is not None:
        return loads(serialized_object=result)

    return None


def get_value(
    sio_client: socketio.AsyncClient,
    loop: asyncio.AbstractEventLoop,
    access_path: str,
) -> Any:
    async def async_get_value() -> Any:
        return await sio_client.call(
            "get_value",
            {
                "access_path": access_path,
            },
        )

    result: SerializedIconObject = asyncio.run_coroutine_threadsafe(
        async_get_value(),
        loop=loop,
    ).result()

    return loads(serialized_object=result)


class Client(pydase.Client):
    def __init__(
        self,
        *,
        url: str,
        block_until_connected: bool = True,
        sio_client_kwargs: dict[str, Any] = {},
    ):
        super().__init__(
            url=url,
            block_until_connected=block_until_connected,
            sio_client_kwargs=sio_client_kwargs,
        )
        del self.proxy

        self._experiment_job_data: dict[int, pd.DataFrame] = {}
        self.scheduler = SchedulerController(self)

    async def _handle_experiment_data(self, data: ExperimentData) -> None:
        logger.debug("Updating experiment data...")
        job_id = data["job_id"]
        data_frame = pd.read_json(StringIO(data["data"]))
        if job_id not in self._experiment_job_data:
            self._experiment_job_data[job_id] = data_frame
        else:
            # Update existing data
            overlap = self._experiment_job_data[job_id].index.intersection(
                data_frame.index
            )

            filtered_data_frame = data_frame.drop(overlap)

            self._experiment_job_data[job_id] = pd.concat(
                [self._experiment_job_data[job_id], filtered_data_frame]
            )

        logger.debug(self._experiment_job_data[job_id])

    async def _handle_connect(self) -> None:
        logger.debug("Connected to '%s' ...", self._url)

    async def _handle_disconnect(self) -> None:
        logger.debug("Disconnected from '%s' ...", self._url)

    async def _setup_events(self) -> None:
        self._sio.on("connect", self._handle_connect)
        self._sio.on("disconnect", self._handle_disconnect)
        self._sio.on("experiment_data", self._handle_experiment_data)

    def get_value(self, full_access_path: str) -> Any:
        return get_value(
            sio_client=self._sio,
            loop=self._loop,
            access_path=full_access_path,
        )

    def set_value(self, full_access_path: str, new_value: Any) -> Any:
        return update_value(
            sio_client=self._sio,
            loop=self._loop,
            access_path=full_access_path,
            value=new_value,
        )

    def trigger_method(
        self,
        full_access_path: str,
        *,
        args: list[Any] = [],
        kwargs: dict[str, Any] = {},
    ) -> Any:
        return trigger_method(
            sio_client=self._sio,
            loop=self._loop,
            access_path=full_access_path,
            args=args,
            kwargs=kwargs,
        )
