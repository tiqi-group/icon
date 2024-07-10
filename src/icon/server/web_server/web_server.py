import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp.web
import click
from pydase.data_service.data_service_observer import DataServiceObserver
from pydase.server.web_server.sio_setup import TriggerMethodDict
from pydase.utils.helpers import get_object_attr_from_path

from icon.serialization.deserializer import loads
from icon.serialization.serializer import dump

if TYPE_CHECKING:
    import socketio  # type: ignore

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
        self.sio: socketio.AsyncServer = kwargs.pop("sio")

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
        async def pre_processing(sid: str, data: Any) -> None:
            logging.debug(
                "Client [%s] sent message %s", click.style(str(sid), fg="cyan"), data
            )

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
