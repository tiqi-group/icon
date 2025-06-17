from __future__ import annotations

import multiprocessing
from pathlib import Path
from typing import Any

import pydase

import icon.server.shared_resource_manager
from icon.config.config import get_config
from icon.server.api.api_service import APIService
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
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

# initialise shared parameter resource
icon.server.shared_resource_manager.parameters_dict.update(
    ParametersRepository.get_influxdbv1_parameters()
)
ParametersRepository.initialize(
    shared_parameters=icon.server.shared_resource_manager.parameters_dict
)

scheduler = Scheduler(
    pre_processing_queue=icon.server.shared_resource_manager.pre_processing_queue
)
scheduler.start()
pre_processing_update_queues: list[multiprocessing.Queue[dict[str, Any]]] = []

pre_processing_update_queues.append(multiprocessing.Queue())
pre_processing_worker = PreProcessingWorker(
    worker_number=0,
    hardware_processing_queue=icon.server.shared_resource_manager.hardware_queue,
    pre_processing_queue=icon.server.shared_resource_manager.pre_processing_queue,
    update_queue=pre_processing_update_queues[0],
    manager=icon.server.shared_resource_manager.manager,
)
pre_processing_worker.start()


pydase.Server(
    APIService(pre_processing_update_queues=pre_processing_update_queues),
    host=get_config().server.host,
    web_port=get_config().server.port,
    frontend_src=Path(__file__).parent / "frontend",
).run()
