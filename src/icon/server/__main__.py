from pathlib import Path

import pydase

import icon.server.queue_manager
from icon.server.api.api_service import APIService
from icon.server.pre_processing.pre_processing import PreProcessingWorker
from icon.server.scheduler.scheduler import Scheduler


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
    pydase.server.web_server.sio_setup.sio_client_manager = (
        icon.server.web_server.web_server.sio_client_manager
    )


patch_serialization_methods()
patch_sio_setup()

scheduler = Scheduler(
    pre_processing_queue=icon.server.queue_manager.pre_processing_queue
)
scheduler.start()
pre_processing_worker = PreProcessingWorker(
    worker_number=0,
    pre_processing_queue=icon.server.queue_manager.pre_processing_queue,
    manager=icon.server.queue_manager.manager,
)
pre_processing_worker.start()


pydase.Server(APIService(), frontend_src=Path(__file__).parent / "frontend").run()
