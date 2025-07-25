import logging
from typing import Any

import click
import pydase
import pydase.data_service.state_manager
import pydase.server.web_server.sio_setup
import socketio  # type: ignore

logger = logging.getLogger(__name__)

pydase_setup_sio_events = pydase.server.web_server.sio_setup.setup_sio_events


class AsyncServer(socketio.AsyncServer):
    controlling_sid: str | None = None
    """Socketio SID of the client controlling the frontend."""


def setup_sio_events(
    sio: AsyncServer,
    state_manager: pydase.data_service.state_manager.StateManager,
) -> None:
    pydase_setup_sio_events(sio, state_manager)

    sio.controlling_sid = None

    @sio.event
    async def connect(sid: str, environ: Any) -> None:
        client_id_header = environ.get("HTTP_X_CLIENT_ID", None)
        remote_username_header = environ.get("HTTP_REMOTE_USER", None)

        if remote_username_header is not None:
            log_id = f"user={click.style(remote_username_header, fg='cyan')}"
        elif client_id_header is not None:
            log_id = f"id={click.style(client_id_header, fg='cyan')}"
        else:
            log_id = f"sid={click.style(sid, fg='cyan')}"

        # send current controlling state to the newly connected client
        await sio.emit(
            "control_state", {"controlling_sid": sio.controlling_sid}, to=sid
        )

        async with sio.session(sid) as session:
            session["client_id"] = log_id
            logger.info("Client [%s] connected", session["client_id"])

    @sio.event
    async def disconnect(sid: str) -> None:
        if sid == sio.controlling_sid:
            sio.controlling_sid = None
            await sio.emit("control_state", {"controlling_sid": None})

        async with sio.session(sid) as session:
            logger.info("Client [%s] disconnected", session["client_id"])

    @sio.event
    async def take_control(sid: str) -> None:
        sio.controlling_sid = sid
        await sio.emit("control_state", {"controlling_sid": sio.controlling_sid})

    @sio.event
    async def release_control(sid: str) -> None:
        if sio.controlling_sid == sid:
            sio.controlling_sid = None
            await sio.emit("control_state", {"controlling_sid": None})


def patch_sio_setup() -> None:
    import pydase.server.web_server.sio_setup  # noqa: PLC0415

    pydase.server.web_server.sio_setup.setup_sio_events = setup_sio_events
