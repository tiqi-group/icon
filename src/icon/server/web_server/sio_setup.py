import logging

import pydase
import pydase.data_service.state_manager
import pydase.server.web_server.sio_setup
import socketio  # type: ignore

from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentData,
    ExperimentDataRepository,
)
from icon.server.exceptions import ValkeyUnavailableError
from icon.server.utils.valkey import is_valkey_available, valkey_url

logger = logging.getLogger(__name__)

pydase_setup_sio_events = pydase.server.web_server.sio_setup.setup_sio_events

if not is_valkey_available():
    raise ValkeyUnavailableError()

sio_client_manager = socketio.AsyncRedisManager(url=valkey_url())


def setup_sio_events(
    sio: socketio.AsyncServer,
    state_manager: pydase.data_service.state_manager.StateManager,
) -> None:
    assert isinstance(sio.manager, type(sio_client_manager)), (
        "Socket.IO manager must use Redis"
    )
    pydase_setup_sio_events(sio, state_manager)

    @sio.event  # type: ignore
    async def get_experiment_data(sid: str, job_id: int) -> ExperimentData:
        return ExperimentDataRepository.get_experiment_data_by_job_id(job_id=job_id)


def patch_sio_setup() -> None:
    import pydase.server.web_server.sio_setup

    pydase.server.web_server.sio_setup.setup_sio_events = setup_sio_events
    pydase.server.web_server.sio_setup.sio_client_manager = sio_client_manager
