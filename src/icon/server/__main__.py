import pydase
import pydase.server.web_server.sio_setup
import socketio

from icon.server.api.api_service import APIService
from icon.server.web_server.web_server import WebServer

sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")

pydase.Server(
    APIService(),
    enable_web=False,
    additional_servers=[
        {
            "server": WebServer,
            "port": 8001,
            "kwargs": {"sio": sio},
        }
    ],
).run()
