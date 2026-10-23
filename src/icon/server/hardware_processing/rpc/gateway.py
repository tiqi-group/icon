"""RPC interface to TIQI gateway devices running the ``gateway-unified`` firmware.

:class:`Gateway` covers the base API (``sys.*``) common to all gateway platforms.
Platform specific APIs build on top of it, like the experiment API of the RFSoC
(:class:`RFSoC`).

Unlike the Zedboard, the gateway speaks an unframed msgpack-rpc stream.
"""

from __future__ import annotations

import contextlib
import logging
import re
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Self

from icon.server.hardware_processing.rpc.client import MsgPackRPCClient
from icon.server.hardware_processing.rpc.errors import RPCError

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)


class GatewayError(RPCError):
    """The device answered, but not the way the client expects."""


class UpdateState(StrEnum):
    """Firmware update state as reported by ``sys.CheckUpdate``."""

    NONE = "none"
    PENDING = "pending"
    TRIAL = "trial"
    DONE = "done"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Session:
    """A client session as listed by ``sys.ListSessions``."""

    client_name: str
    client_ip: str
    client_port: int
    """TCP source port of the client."""


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Parsed answer of ``sys.GetDeviceInfo``."""

    board_model: str
    board_serial_number: str
    board_mac_address: str
    firmware_build: str
    """Build date and time of the firmware."""
    firmware_version: str
    gateware_version: str
    submodule_versions: dict[str, str]
    """Git hash per submodule name."""

    @classmethod
    def parse(cls, info: Any) -> Self:
        try:
            return cls(
                board_model=info["board_model"],
                board_serial_number=info["board_serial_number"],
                board_mac_address=info["board_mac_address"],
                firmware_build=info["firmware_build"],
                firmware_version=info["firmware_version"],
                gateware_version=info["gateware_version"],
                submodule_versions=dict(info["submodule_versions"]),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise GatewayError(f"unexpected device info {info!r}") from e


class Gateway:
    """Direct RPC interface to the base API common to all gateway platforms.

    Several endpoints are still placeholders in the firmware and answer with an error
    until they are implemented. Endpoints whose arguments the firmware has yet to define
    are wrapped without arguments for now.
    """

    def __init__(
        self,
        hostname: str,
        port: int,
        timeout: float | None = 5,
    ) -> None:
        self.hostname = hostname
        self.port = port
        self._timeout = timeout
        self._client = MsgPackRPCClient(
            hostname=hostname, port=port, timeout=timeout, framed=False
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}[{self._client}]"

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.disconnect()

    def connect(self) -> None:
        """Establish a connection to the device.

        Raises:
            ConnectionRefusedError: if the peer does not accept the connection. Probably
                not listening.
            OSError: if the host cannot be reached or resolved.
        """
        self._client.connect()

    def disconnect(self) -> None:
        self._client.disconnect()

    @property
    def is_connected(self) -> bool:
        """Whether the underlying socket is up."""
        return self._client.is_connected

    def _invoke(self, method: str, *values: Any, timeout: float | None = None) -> Any:
        """Private wrapper for RPC invocations. Use specialized methods instead."""
        return self._client.call(method, *values, timeout=timeout)

    # *** RPC

    def help(self, name: str = "") -> list[str]:
        """Describe the RPC function ``name``.

        ``"all"`` describes every function, any other unknown name lists them.
        """
        return self._invoke("rpc.Help", name)

    # *** Connection

    def register_session(self, client_name: str) -> None:
        """Register the session of this connection by its client name, or rename it if already registered.

        The client name has at most 256 characters. The device removes the session when
        the client disconnects or times out.
        """
        # TODO: return the API version of the device once the firmware does
        self._invoke("sys.RegisterSession", client_name)

    def list_sessions(self) -> list[Session]:
        """Enumerate all registered client sessions."""
        sessions = self._invoke("sys.ListSessions")
        try:
            return [Session(name, ip, port) for name, ip, port in sessions]
        except (TypeError, ValueError) as e:
            raise GatewayError(f"unexpected sessions {sessions!r}") from e

    def loopback(self, message: Any) -> Any:
        """Return ``message`` unchanged, as a simple liveness check."""
        return self._invoke("sys.Loopback", message)

    # *** Identity

    def get_device_info(self) -> DeviceInfo:
        """Return the board model, serial number and MAC address and the firmware, gateware and submodule versions."""
        return DeviceInfo.parse(self._invoke("sys.GetDeviceInfo"))

    def get_capabilities(self) -> Any:
        """Return the supported methods, notifications and limits of the device, which can change at runtime."""
        return self._invoke("sys.GetCapabilities")

    # *** Health

    def get_health(self) -> dict[str, Any]:
        """Return the device health.

        Holds the ``cpu_temperature`` (°C) and ``cpu_voltage`` (V), the ``clk_status``
        (external, internal, unlocked or off), the ``sysmon_alarms`` flags, the
        ``uptime`` (µs), the ``current_time``, the ``reset_reason``, the
        ``reset_count`` since power-on, the persistent ``boot_count``, the ``heap`` and
        ``stack`` usage and the lwIP statistics as ``network``.
        """
        return self._invoke("sys.GetHealth")

    def get_status(self) -> Any:
        """Return the lightweight device status (OK, or ERROR if an error is pending), as reflected by the LED."""
        return self._invoke("sys.GetStatus")

    def consume_error(self) -> Any:
        """Acknowledge and clear the sticky ERROR register."""
        return self._invoke("sys.ConsumeError")

    # *** Lifecycle

    def reboot(self) -> None:
        """Reboot the device, which drops the connection."""
        # The device resets before it can answer.
        with contextlib.suppress(TimeoutError, ConnectionError):
            self._invoke("sys.Reboot")

    # *** Firmware

    def update_firmware(
        self, path: str, data: bytes, timeout: float | None = None
    ) -> None:
        """Upload a new firmware image and stage it for the upgrade on the next reboot."""
        self._invoke("sys.UpdateFirmware", path, data, timeout=timeout)

    def check_update(self) -> UpdateState:
        """Return the firmware update state, which the client must check on every connect."""
        state = self._invoke("sys.CheckUpdate")
        try:
            return UpdateState(state)
        except ValueError as e:
            raise GatewayError(f"unknown firmware update state {state!r}") from e

    def confirm_update(self) -> None:
        """Confirm that the updated firmware runs and is reachable by a client.

        Must be done when the update state is :attr:`UpdateState.TRIAL`.
        """
        # TODO: drop the argument once the firmware sets DONE by itself
        self._invoke("sys.ConfirmUpdate", UpdateState.DONE.value)

    # *** Logs/Diag

    def set_log_level(self) -> None:
        """Change the on-device logging verbosity. Arguments are yet to be defined by the firmware."""
        self._invoke("sys.SetLogLevel")

    def get_logs(self) -> Any:
        """Return the log entries starting at the given index and offset. Arguments are yet to be defined by the firmware."""
        return self._invoke("sys.GetLogs")

    def get_log_file(self) -> Any:
        """Return the log file, including the logs dumped on reset or exception and the runtime logs."""
        return self._invoke("sys.GetLogFile")

    def run_self_test(self) -> Any:
        """Run the device self test, which can be cancelled between sub-tests."""
        return self._invoke("sys.RunSelfTest")

    def peek(self) -> Any:
        """Read a memory region. Arguments are yet to be defined by the firmware."""
        return self._invoke("sys.Peek")

    def poke(self) -> None:
        """Write a memory region. Arguments are yet to be defined by the firmware."""
        self._invoke("sys.Poke")

    # *** Config

    def get_config(self) -> Any:
        """Read the config keys that are in effect or would take effect on the next apply."""
        return self._invoke("sys.GetConfig")

    def set_config(self) -> None:
        """Write volatile config keys without applying them. Arguments are yet to be defined by the firmware."""
        self._invoke("sys.SetConfig")

    def commit_config(self) -> None:
        """Commit the previously set volatile config into the persistent memory."""
        self._invoke("sys.CommitConfig")

    def restore_config(self) -> None:
        """Load the configuration from the persistent store without applying it."""
        self._invoke("sys.RestoreConfig")

    def reset_config(self) -> None:
        """Restore the persistent config (U-Boot environment and application config) to the factory defaults."""
        self._invoke("sys.ResetConfig")

    def apply_config(self) -> None:
        """Make the configuration take effect."""
        self._invoke("sys.ApplyConfig")

    # *** Time

    def get_time(self) -> str:
        """Return the device clock time and its source."""
        return self._invoke("sys.GetTime")

    def set_time(self) -> None:
        """Update the device RTC time. Arguments are yet to be defined by the firmware."""
        self._invoke("sys.SetTime")

    # *** File system

    def read_file(self, path: str) -> str:
        """Read the text file at ``path`` on the update partition.

        Bound by the hardware platforms, not by the emulator.
        """
        return self._invoke("fs.ReadFile", path)

    def write_file(self, path: str, data: str) -> None:
        """Write the text file at ``path`` on the update partition.

        Bound by the hardware platforms, not by the emulator.
        """
        self._invoke("fs.WriteFile", path, data)

    # *** Platform

    def sleep(self, seconds: int) -> None:
        """Block the device for ``seconds``.

        Bound by every platform, although not part of the base API.
        """
        timeout = None if self._timeout is None else self._timeout + seconds
        self._invoke("sys.Sleep", seconds, timeout=timeout)


class TaskStatus(StrEnum):
    """State of the experiment task on the device."""

    IDLE = "IDLE"
    """No task is set up."""
    SETUP = "SETUP"
    """A task is set up and waits to be started."""
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    """The task has finished and its results wait to be collected."""


class TaskNotification(StrEnum):
    """Notifications the device sends to the client that started the task when it ends."""

    FINISHED = "exp::FINISHED"
    ABORTED = "exp::ABORTED"


_TASK_STATUS_PATTERN = re.compile(
    r"Status (?P<status>IDLE|SETUP|RUNNING|FINISHED), "
    r"executed (?P<executed>\d+) / (?P<requested>\d+) shots in (?P<duration>-?\d+) ms"
)


@dataclass(frozen=True, slots=True)
class TaskStatusReport:
    """Parsed answer of ``exp.GetTaskStatus``."""

    status: TaskStatus
    executed_shots: int
    requested_shots: int
    duration_ms: int
    """Run time of the task. Only meaningful once it has finished."""

    @classmethod
    def parse(cls, text: str) -> Self:
        match = _TASK_STATUS_PATTERN.match(text)
        if match is None:
            raise GatewayError(f"unexpected task status {text!r}")
        return cls(
            status=TaskStatus(match["status"]),
            executed_shots=int(match["executed"]),
            requested_shots=int(match["requested"]),
            duration_ms=int(match["duration"]),
        )


@dataclass(frozen=True, slots=True)
class TaskResult:
    """Raw results of a finished task."""

    data: dict[str, list[list[float]]]
    """Values per data channel name and shot index.

    The names are prefixed with ``shot/``, ``readout/`` or ``vector/`` by channel type.
    """
    failed: dict[str, list[list[float]]]
    """Values of the failed (and repeated) shots per data channel name."""
    log: str


class RFSoC(Gateway):
    """Direct RPC interface to the RFSoC (ZCU216) gateway.

    Adds the experiment API, which runs a JSON sequence as a task. Each sequence run takes
    the following steps:

        rfsoc.setup_task(sequence_json)
        rfsoc.start_task()
        rfsoc.wait_for_task()
        results = rfsoc.get_task_results()
    """

    # *** Identity

    def get_device_id(self) -> str:
        """Return the device id, which is the hostname from the boot environment."""
        return self._invoke("exp.GetDeviceID")

    # *** Task

    def setup_task(self, sequence: str) -> None:
        """Parse the JSON ``sequence`` and prepare the hardware. Fails if a task is not IDLE."""
        self._invoke("exp.SetupTask", sequence)

    def start_task(self) -> None:
        """Start the task set up by :meth:`setup_task`. Fails if the task is not SETUP.

        Only this client is notified when the task ends, see :meth:`wait_for_task`.
        """
        # Discard the notifications of earlier tasks. The device sends them before it
        # answers the next request, so the last call has buffered them all.
        self._client.consume_notifications()
        self._invoke("exp.StartTask")

    def get_task_status(self) -> TaskStatusReport:
        return TaskStatusReport.parse(self._invoke("exp.GetTaskStatus"))

    def get_task_results(self) -> TaskResult:
        """Collect the results of the finished task, which returns the device to IDLE.

        Fails if the task is not FINISHED, or (after returning to IDLE) if it gave up on
        too many failed shots.
        """
        match self._invoke("exp.GetTaskResults"):
            case [dict() as data, dict() as failed, str() as log]:
                return TaskResult(data=data, failed=failed, log=log)
            case _:
                raise GatewayError("unexpected format of the task results")

    def wait_for_task(
        self, timeout: float | None = None, poll_interval: float = 0.001
    ) -> bool:
        """Poll the notifications until the device notifies that the task has finished.

        The device notifies the client that started the task once, when the task has
        finished or was aborted. The notification is lost if the notification buffer of
        the client overflows meanwhile, so poll :meth:`get_task_status` when this returns
        ``False``.

        Args:
            timeout: Maximum time to wait, in seconds. Uses the default timeout when
                omitted.
            poll_interval: Seconds between polls of the notifications.

        Returns:
            Whether the task has finished, ``False`` if no notification arrived within
            ``timeout``.

        Raises:
            GatewayError: if the task was aborted meanwhile.
        """
        _timeout = self._timeout if timeout is None else timeout
        deadline = None if _timeout is None else time.monotonic() + _timeout
        while True:
            for _, params in self._client.consume_notifications():
                match params:
                    case [TaskNotification.FINISHED]:
                        return True
                    case [TaskNotification.ABORTED]:
                        raise GatewayError("the task was aborted")
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(poll_interval)

    def abort_task(self) -> None:
        """Abort the current task in any state and reset the experiment and hardware to IDLE."""
        self._invoke("exp.AbortTask")

    # *** Digital outputs

    def set_digital_output_override(self, mask: int, state: int) -> None:
        """Force the digital outputs selected by ``mask`` to ``state``."""
        self._invoke(
            "exp.SetDigitalOutputOverride", mask & 0xFFFFFFFF, state & 0xFFFFFFFF
        )

    def get_digital_output_override(self) -> tuple[int, int]:
        """Return the override ``(mask, state)`` of the digital outputs."""
        mask, state = self._invoke("exp.GetDigitalOutputOverride")
        return mask, state

    # *** Experiment config

    def get_experiment_timeout(self) -> int:
        """Seconds after which a task gives up repeating failed shots."""
        return self._invoke("exp.GetExperimentTimeout")

    def set_experiment_timeout(self, seconds: int) -> None:
        self._invoke("exp.SetExperimentTimeout", seconds)

    def get_errors_before_recrystallization(self) -> int:
        """Errors required before an error triggers recrystallization."""
        return self._invoke("exp.GetErrorsBeforeRecrystalization")

    def set_errors_before_recrystallization(self, count: int) -> None:
        self._invoke("exp.SetErrorsBeforeRecrystalization", count)

    def get_recrystallization_fraction(self) -> float:
        """Maximum fraction of shots requiring recrystallization."""
        return self._invoke("exp.GetRecrystalizationFraction")

    def set_recrystallization_fraction(self, fraction: float) -> None:
        self._invoke("exp.SetRecrystalizationFraction", fraction)

    def get_line_trigger_delay(self) -> int:
        return self._invoke("exp.GetLineTriggerDelay")

    def set_line_trigger_delay(self, value: int) -> None:
        self._invoke("exp.SetLineTriggerDelay", value)

    def get_start_pad_delay(self) -> int:
        return self._invoke("exp.GetStartPadDelay")

    def set_start_pad_delay(self, value: int) -> None:
        self._invoke("exp.SetStartPadDelay", value)

    def get_start_pulse_delay(self) -> int:
        return self._invoke("exp.GetStartPulseDelay")

    def set_start_pulse_delay(self, value: int) -> None:
        self._invoke("exp.SetStartPulseDelay", value)

    def get_start_digital_delay(self) -> int:
        return self._invoke("exp.GetStartDigitalDelay")

    def set_start_digital_delay(self, value: int) -> None:
        self._invoke("exp.SetStartDigitalDelay", value)

    def get_start_backplane_delay_ticks(self) -> int:
        """Backplane start delay in pulseway ticks."""
        return self._invoke("exp.GetStartBPDelayTicks")

    def set_start_backplane_delay_ticks(self, ticks: int) -> None:
        self._invoke("exp.SetStartBPDelayTicks", ticks)

    def get_pmt_timeout(self) -> int:
        return self._invoke("exp.GetPmtTimeout")

    def set_pmt_timeout(self, value: int) -> None:
        self._invoke("exp.SetPmtTimeout", value)

    def get_line_trigger_enabled(self) -> bool:
        return self._invoke("exp.GetLineTriggerEnable")

    def set_line_trigger_enabled(self, *, enabled: bool) -> None:
        self._invoke("exp.SetLineTriggerEnable", enabled)

    # *** Platform

    def measure_watchdog_time(
        self, counter_reset_value: int, prescale: int, timeout: float | None = None
    ) -> int:
        """Run the watchdog until it expires and return the elapsed microseconds.

        Blocks the device meanwhile. ``prescale`` selects the clock divider 8, 64, 512
        or 4096 by 0 to 3.
        """
        return self._invoke(
            "sys.MeasureWatchdogTime", counter_reset_value, prescale, timeout=timeout
        )
