import logging

import click
import pydase.data_service.state_manager
import pydase.server.web_server.sio_setup
import socketio  # type: ignore

logger = logging.getLogger(__name__)

pydase_setup_sio_events = pydase.server.web_server.sio_setup.setup_sio_events


def setup_sio_events(
    sio: socketio.AsyncServer,
    state_manager: pydase.data_service.state_manager.StateManager,
) -> None:
    pydase_setup_sio_events(sio, state_manager)

    @sio.event  # type: ignore
    async def get_experiment_data(sid: str, experiment_id: str) -> None:
        # First join room if exists to subscribe to updates
        if experiment_id in sio.manager.rooms:
            logger.debug(
                "Client [%s] joined room %s",
                click.style(str(sid), fg="cyan"),
                experiment_id,
            )
            await sio.enter_room(sid, experiment_id)
        else:
            logging.debug(
                "Client [%s] requested to join room %s but it does not exist.",
                click.style(str(sid), fg="cyan"),
                experiment_id,
            )

        # Then serve all the data that has been collected already
        # The client will not miss anything then.
        await sio.emit(
            "experiment_data", get_data_by_experiment_id(experiment_id), to=sid
        )

    @sio.event  # type: ignore
    async def stop_experiment_data_stream(sid: str, experiment_id: str) -> None:
        logging.debug(
            "Client [%s] left room %s",
            click.style(str(sid), fg="cyan"),
            experiment_id,
        )
        await sio.leave_room(sid, experiment_id)
