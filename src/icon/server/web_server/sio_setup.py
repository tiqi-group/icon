import logging

import pydase
import pydase.data_service.state_manager
import pydase.server.web_server.sio_setup
import socketio  # type: ignore

from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentData,
    ExperimentDataRepository,
)

logger = logging.getLogger(__name__)

pydase_setup_sio_events = pydase.server.web_server.sio_setup.setup_sio_events


def setup_sio_events(
    sio: socketio.AsyncServer,
    state_manager: pydase.data_service.state_manager.StateManager,
) -> None:
    pydase_setup_sio_events(sio, state_manager)

    @sio.event  # type: ignore
    async def get_experiment_data(sid: str, job_id: int) -> ExperimentData:
        return ExperimentDataRepository.get_experiment_data_by_job_id(job_id=job_id)


def patch_sio_setup() -> None:
    import pydase.server.web_server.sio_setup  # noqa: PLC0415

    pydase.server.web_server.sio_setup.setup_sio_events = setup_sio_events
