import logging

import click
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
sio_client_manager = socketio.AsyncRedisManager()


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
        # First join room if exists to subscribe to updates
        job_room = f"experiment_{job_id}"
        logger.debug(
            "Client [%s] joined room %s",
            click.style(str(sid), fg="cyan"),
            job_room,
        )
        await sio.enter_room(sid, job_room)

        return ExperimentDataRepository.get_experiment_data_by_job_id(job_id=job_id)

    @sio.event  # type: ignore
    async def stop_experiment_data_stream(sid: str, job_id: int) -> None:
        job_room = f"experiment_{job_id}"
        logger.debug(
            "Client [%s] left room %s",
            click.style(str(sid), fg="cyan"),
            job_room,
        )
        await sio.leave_room(sid, job_room)


def patch_sio_setup() -> None:
    import pydase.server.web_server.sio_setup

    pydase.server.web_server.sio_setup.setup_sio_events = setup_sio_events
    pydase.server.web_server.sio_setup.sio_client_manager = sio_client_manager
