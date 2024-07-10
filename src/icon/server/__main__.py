import pydase
import pydase.server.web_server.sio_setup

from icon.server.api.api_service import APIService
from icon.server.web_server.web_server import WebServer

pydase.Server(
    APIService(),
    enable_web=False,
    additional_servers=[
        {
            "server": WebServer,
            "port": 8001,
            "kwargs": {},
        }
    ],
).run()
