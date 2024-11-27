from pathlib import Path

import pydase

import icon.server.queue_manager
from icon.server.api.api_service import APIService
from icon.server.pre_processing.pre_processing import PreProcessingWorker
from icon.server.scheduler.scheduler import Scheduler
from icon.server.web_server.sio_setup import patch_sio_setup


def patch_serialization_methods() -> None:
    import pydase.server.web_server.api.v1.endpoints
    import pydase.server.web_server.sio_setup

    import icon.serialization

    pydase.server.web_server.sio_setup.dump = icon.serialization.dump  # type: ignore
    pydase.server.web_server.api.v1.endpoints.loads = icon.serialization.loads
    pydase.server.web_server.api.v1.endpoints.Serializer = (
        icon.serialization.IconSerializer
    )


patch_sio_setup()
patch_serialization_methods()

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
