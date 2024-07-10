import asyncio
import logging
from pathlib import Path
from typing import Any

import aiohttp.web
import click
import socketio  # type: ignore
from pydase.data_service.data_service_observer import DataServiceObserver
from pydase.server.web_server.sio_setup import TriggerMethodDict, UpdateDict
from pydase.utils.helpers import get_object_attr_from_path

from icon.serialization.deserializer import loads
from icon.serialization.serializer import dump
from icon.serialization.types import SerializedIconObject

logger = logging.getLogger(__name__)


class WebServer:
    """
    Arguments:
        sio: socketio.AsyncServer
            socketio server instance. Need to inject to be able to use it elsewhere.
    """

    def __init__(
        self,
        data_service_observer: DataServiceObserver,
        host: str,
        port: int,
        **kwargs: Any,
    ) -> None:
        self.observer = data_service_observer
        self.state_manager = self.observer.state_manager
        self.service = self.state_manager.service
        self.port = port
        self.host = host
        self.frontend_src: Path = Path(__file__).parent.parent / "frontend"
        self._loop: asyncio.AbstractEventLoop
        self.sio = socketio.AsyncServer(client_manager=socketio.AsyncRedisManager())

    async def serve(self) -> None:
        async def index(request: aiohttp.web.Request) -> aiohttp.web.FileResponse:
            return aiohttp.web.FileResponse(self.frontend_src / "index.html")

        self._loop = asyncio.get_running_loop()
        await self._setup_socketio_events()

        app = aiohttp.web.Application()

        self.sio.attach(app, socketio_path="/ws/socket.io")

        app.router.add_static("/assets", self.frontend_src / "assets")
        app.router.add_get(r"/", index)
        app.router.add_get(r"/{tail:.*}", index)

        await aiohttp.web._run_app(
            app, host=self.host, port=self.port, print=logger.info
        )

    async def _setup_socketio_events(self) -> None:
        @self.sio.event  # type: ignore
        async def connect(sid: str, environ: Any) -> None:
            logging.debug("Client [%s] connected", click.style(str(sid), fg="cyan"))

        @self.sio.event  # type: ignore
        async def join_room(sid: str, room: str) -> None:
            logging.debug(
                "Client [%s] joins room %s", click.style(str(sid), fg="cyan"), room
            )
            await self.sio.enter_room(sid, room)

        @self.sio.event  # type: ignore
        async def leave_room(sid: str, room: str) -> None:
            logging.debug(
                "Client [%s] leaves room %s", click.style(str(sid), fg="cyan"), room
            )
            await self.sio.leave_room(sid, room)

        @self.sio.event  # type: ignore
        async def disconnect(sid: str) -> None:
            logging.debug("Client [%s] disconnected", click.style(str(sid), fg="cyan"))

        @self.sio.event
        async def trigger_method(sid: str, data: TriggerMethodDict) -> Any:
            try:
                method = get_object_attr_from_path(
                    self.state_manager.service, data["access_path"]
                )
                args = loads(data["args"])
                kwargs: dict[str, Any] = loads(data["kwargs"])
                return dump(method(*args, **kwargs))
            except Exception as e:
                logger.error(e)
                return dump(e)

        @self.sio.event
        async def update_value(
            sid: str, data: UpdateDict
        ) -> SerializedIconObject | None:  # type: ignore
            path = data["access_path"]

            try:
                self.state_manager.set_service_attribute_value_by_path(
                    path=path, serialized_value=data["value"]
                )
                return None
            except Exception as e:
                logger.exception(e)
                return dump(e)

        @self.sio.event
        async def get_value(sid: str, access_path: str) -> SerializedIconObject:
            try:
                return self.state_manager._data_service_cache.get_value_dict_from_cache(
                    access_path
                )
            except Exception as e:
                logger.exception(e)
                return dump(e)
