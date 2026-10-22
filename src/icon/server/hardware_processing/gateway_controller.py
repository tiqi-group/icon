import logging
import socket
from typing import Any, Final, Generic, TypeVar

from icon.server.hardware_processing.hardware_controller import (
    HardwareController,
    StatusFlag,
)
from icon.server.hardware_processing.rpc.errors import RPCError, RPCResponseError
from icon.server.hardware_processing.rpc.gateway import Gateway, UpdateState

logger = logging.getLogger(__name__)

GatewayT = TypeVar("GatewayT", bound=Gateway)

CLIENT_NAME: Final = f"ICON@{socket.gethostname()}"
"""Client name of the sessions ICON registers on gateway devices."""


class GatewayController(HardwareController, Generic[GatewayT]):
    """Base for the Hardware Controllers of gateway devices.

    Handles the connection and the base API common to all gateway platforms. Identifying
    the device (:meth:`query_device_id`) and running sequences (:meth:`send`,
    :meth:`run`, :meth:`receive`) is up to the platform.
    """

    def __init__(self, gateway: GatewayT) -> None:
        """Initialise the controller.

        Args:
            gateway: RPC interface to the device.
        """
        self._gateway = gateway

    def connect(self) -> None:
        try:
            self._gateway.connect()
        except OSError as e:
            logger.warning("Could not connect to %s: %s", self.display_name, e)
            return
        logger.info("Connected to %r", self._gateway)
        self._register_session()
        self._confirm_firmware_update()

    def _register_session(self) -> None:
        """Register the session of the new connection, which names ICON as its client."""
        try:
            self._gateway.register_session(CLIENT_NAME)
        except (RPCError, OSError) as e:
            logger.warning(
                "Could not register the session on %s: %s", self.display_name, e
            )

    def _confirm_firmware_update(self) -> None:
        """Check the firmware update state, as the base API requires on every connect.

        A trial firmware is confirmed, since the connection shows that it runs and is
        reachable.
        """
        try:
            state = self._gateway.check_update()
            if state is UpdateState.TRIAL:
                logger.info("Confirming the trial firmware of %s", self.display_name)
                self._gateway.confirm_update()
            elif state in (UpdateState.FAILED, UpdateState.ROLLED_BACK):
                logger.warning("Firmware update of %s: %s", self.display_name, state)
        except RPCResponseError as e:
            logger.info(
                "Firmware update state of %s is unavailable: %s", self.display_name, e
            )
        except (RPCError, OSError) as e:
            logger.warning(
                "Could not check the firmware update state of %s: %s",
                self.display_name,
                e,
            )

    def _ensure_connected(self) -> None:
        if not self.connected:
            self.connect()
        if not self.connected:
            raise RuntimeError(
                f"Could not connect to {self.display_name} while trying to run a command"
            )

    @property
    def connected(self) -> bool:
        return self._gateway.is_connected

    @property
    def display_name(self) -> str:
        """Representative name which also must be available when the device is not reachable."""
        kind = type(self).__name__.removesuffix("Controller")
        return f"{kind}@{self._gateway.hostname}:{self._gateway.port}"

    def status(self) -> tuple[StatusFlag, str, Any]:
        try:
            status = self._gateway.get_status()
        except (RPCError, OSError) as e:
            return (StatusFlag.UNKNOWN, str(e), None)
        flag = StatusFlag.SUCCESS if status == "OK" else StatusFlag.ERROR
        return (flag, str(status), status)
