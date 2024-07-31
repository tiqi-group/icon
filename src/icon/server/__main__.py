import multiprocessing
from pathlib import Path

import pydase

import icon.server.pre_processing.pre_processing
from icon.server.api.api_service import APIService


def patch_serialization_methods() -> None:
    import pydase.server.web_server.api.v1.endpoints
    import pydase.server.web_server.sio_setup

    import icon.serialization

    pydase.server.web_server.sio_setup.dump = icon.serialization.dump  # type: ignore
    pydase.server.web_server.api.v1.endpoints.loads = icon.serialization.loads
    pydase.server.web_server.api.v1.endpoints.Serializer = (
        icon.serialization.IconSerializer
    )


def patch_sio_setup() -> None:
    import pydase.server.web_server.sio_setup

    import icon.server.web_server.web_server

    pydase.server.web_server.sio_setup.setup_sio_events = (
        icon.server.web_server.web_server.setup_sio_events
    )


patch_serialization_methods()
patch_sio_setup()

p = multiprocessing.Process(target=icon.server.pre_processing.pre_processing.task)
p.start()


pydase.Server(APIService(), frontend_src=Path(__file__).parent / "frontend").run()
