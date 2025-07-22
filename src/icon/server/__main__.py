from __future__ import annotations

import multiprocessing
from pathlib import Path
from typing import TYPE_CHECKING

import icon.server.shared_resource_manager
import icon.server.web_server.icon_server
from icon.config.config import get_config
from icon.server.api.api_service import APIService
from icon.server.hardware_processing.hardware_processing import HardwareProcessingWorker
from icon.server.pre_processing.pre_processing import PreProcessingWorker
from icon.server.scheduler.scheduler import Scheduler

if TYPE_CHECKING:
    from icon.server.utils.types import UpdateQueue


def patch_serialization_methods() -> None:
    import pydase.server.web_server.api.v1.endpoints
    import pydase.server.web_server.sio_setup

    import icon.serialization

    pydase.server.web_server.sio_setup.dump = icon.serialization.dump  # type: ignore
    pydase.server.web_server.api.v1.endpoints.loads = icon.serialization.loads
    pydase.server.web_server.api.v1.endpoints.Serializer = (
        icon.serialization.IconSerializer
    )


patch_serialization_methods()

scheduler = Scheduler(
    pre_processing_queue=icon.server.shared_resource_manager.pre_processing_queue
)
scheduler.start()

number_of_pre_processing_workers = get_config().server.pre_processing.workers
pre_processing_update_queues: list[multiprocessing.Queue[UpdateQueue]] = []

for i in range(number_of_pre_processing_workers):
    pre_processing_update_queues.append(multiprocessing.Queue())
    pre_processing_worker = PreProcessingWorker(
        worker_number=i,
        hardware_processing_queue=icon.server.shared_resource_manager.hardware_processing_queue,
        pre_processing_queue=icon.server.shared_resource_manager.pre_processing_queue,
        update_queue=pre_processing_update_queues[i],
        manager=icon.server.shared_resource_manager.manager,
    )
    pre_processing_worker.start()

hardware_processing_worker = HardwareProcessingWorker(
    hardware_processing_queue=icon.server.shared_resource_manager.hardware_processing_queue,
    manager=icon.server.shared_resource_manager.manager,
)
hardware_processing_worker.start()


icon.server.web_server.icon_server.IconServer(
    APIService(pre_processing_update_queues=pre_processing_update_queues),
    host=get_config().server.host,
    web_port=get_config().server.port,
    frontend_src=Path(__file__).parent / "frontend",
).run()
