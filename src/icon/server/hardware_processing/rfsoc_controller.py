from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import socket
import threading
import weakref
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Final, Self

from qendra.device_client import (
    ApiVersionError,
    DeviceError,
    ExperimentTask,
    PulseClient,
    RPCError,
    RPCResponseError,
    TaskAbortedError,
    UpdateState,
)
from qendra.device_client.config import DEFAULT_CALL_TIMEOUT
from qendra.device_client.sync import SyncWrapper

from icon.server.data_access.experiment_data import Readouts
from icon.server.hardware_processing.hardware_controller import (
    HardwareController,
    StatusFlag,
)

if TYPE_CHECKING:
    from qendra.device_client import TaskResult

logger = logging.getLogger(__name__)

CLIENT_NAME: Final = f"ICON@{socket.gethostname()}"
"""Client name of the sessions ICON registers on the devices."""

SEQUENCE_TIME_FACTOR: Final = 1.5
"""Factor on the time the shots of a task take, to allow for the overhead per shot."""


# *** Event loop
#
# The device client is asyncio, while the Hardware Controllers are called from the threads
# of the hardware worker and the status checks. Each controller therefore runs its client
# on the event loop of a SyncWrapper, in a daemon thread of its own.


def _close(sync: SyncWrapper[PulseClient]) -> None:
    """Disconnect the client of a dropped controller and shut its event loop down."""
    try:
        sync.run(sync.client.disconnect())
    except (RuntimeError, OSError) as e:
        # RuntimeError: the wrapper is shut down, e.g. in a forked process
        logger.debug("Could not disconnect %r: %s", sync.client, e)
    finally:
        sync.shutdown()


def _close_soon(sync: SyncWrapper[PulseClient]) -> None:
    """Close the wrapper of a dropped controller on a thread of its own.

    The controller can be dropped on any thread, among them the one running the event
    loop of the wrapper, which cannot wait for that loop.
    """
    threading.Thread(
        target=_close, args=(sync,), name=f"close {sync!r}", daemon=True
    ).start()


class RFSoCController(HardwareController):
    """Qendra Pulse (ZCU216 RFSoC) Hardware Controller using the experiment API of the device.

    A sequence runs as in a task: :meth:`send` loads it into the sequence slot of the device,
    :meth:`run` starts a task with it and :meth:`receive` waits for the task to finish, which
    the device notifies with its results. The device stays responsive while the task runs,
    so it can be aborted.

    The client runs on the event loop of a :class:`~qendra.device_client.sync.SyncWrapper`
    of its own. Dropping the controller closes the connection and stops the event loop.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        timeout: float = DEFAULT_CALL_TIMEOUT,
        task_timeout_margin: float = 5,
    ) -> None:
        """Initialise the controller.

        Args:
            host: Hostname of the Qendra Pulse device.
            port: Port the RPC server of the device listens on.
            timeout: Timeout in seconds for RPC calls.
            task_timeout_margin: Seconds to wait for a task on top of
                :data:`SEQUENCE_TIME_FACTOR` times the time its shots take, before
                aborting it.
        """
        self._client = PulseClient(hostname=host, port=port, timeout=timeout)
        self._sync = SyncWrapper(self._client)
        """Runs the coroutines of :attr:`_client` on its event loop."""
        self._finalizer = weakref.finalize(self, _close_soon, self._sync)
        # The process ends the connection at exit, where no thread can be started
        # (atexit is a property, which typeshed declares next to empty __slots__)
        self._finalizer.atexit = False  # type: ignore[misc]
        self._task_timeout_margin = task_timeout_margin
        self._task_timeout = task_timeout_margin
        self._sequence_id: str | None = None
        """The sequence :meth:`send` loaded, which :meth:`run` takes."""
        self._task: ExperimentTask | None = None
        """The task :meth:`run` started, which :meth:`receive` takes."""
        self._device_id: str | None = None
        self._channel_layout = ChannelLayout()

    # *** Connection

    def connect(self) -> None:
        self._sync.run(self._connect())

    async def _connect(self) -> None:
        """Connect, register the session, confirm a firmware update and query the device id.

        Logs and returns if the device cannot be reached; see :attr:`connected`.
        """
        try:
            # Also checks the interface version of the firmware
            await self._client.connect()
        except ApiVersionError as e:
            logger.error("Could not connect to %s: %s", self.display_name, e)  # noqa: TRY400
            return
        except (RPCError, OSError) as e:
            logger.warning("Could not connect to %s: %s", self.display_name, e)
            return
        logger.info("Connected to %r", self._client)
        await self._register_session()
        await self._confirm_firmware_update()
        try:
            self._device_id = await self._client.get_device_id()
        except (RPCError, OSError) as e:
            logger.warning(
                "Could not query the device id of %s: %s", self.display_name, e
            )

    async def _register_session(self) -> None:
        """Register the session of the new connection, which names ICON as its client."""
        try:
            await self._client.register_session(CLIENT_NAME)
        except (RPCError, OSError) as e:
            logger.warning(
                "Could not register the session on %s: %s", self.display_name, e
            )

    async def _confirm_firmware_update(self) -> None:
        """Check the firmware update state, as the base API requires on every connect.

        A trial firmware is confirmed, since the connection shows that it runs and is
        reachable.
        """
        try:
            state = await self._client.check_update()
            if state is UpdateState.TRIAL:
                logger.info("Confirming the trial firmware of %s", self.display_name)
                await self._client.confirm_update()
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
        return self._client.is_connected

    @property
    def display_name(self) -> str:
        """Representative name which also must be available when the device is not reachable."""
        return f"RFSoC@{self._client.hostname}:{self._client.port}"

    def query_device_id(self) -> str | None:
        return self._device_id

    def status(self) -> tuple[StatusFlag, str, Any]:
        # TODO: report sys.getStatus once the firmware implements it
        try:
            health = self._sync.run(self._client.get_health())
        except (RPCError, OSError) as e:
            return (StatusFlag.UNKNOWN, str(e), None)
        return (StatusFlag.SUCCESS, "OK", health)

    # *** Task

    def send(self, data: str) -> None:
        """The data is loaded with the SHA-256 of ``data`` as its sequence id.

        If the device is already occupied with a task or a loaded sequence, any task is
        aborted and any sequence removed before retry.
        """
        self._ensure_connected()
        header = _decode_header(data)
        self._task_timeout = (
            self._task_timeout_margin + SEQUENCE_TIME_FACTOR * _shots_time(header)
        )
        # TODO: drop together with the Zedboard compatibility
        self._channel_layout = ChannelLayout.from_header(
            header, device_id=self._device_id
        )
        self._sequence_id = None
        sequence_id = hashlib.sha256(data.encode()).hexdigest()
        try:
            self._sync.run(self._client.load_sequence(sequence_id, data))
        except RPCResponseError:
            self._sync.run(self._replace_sequence(sequence_id, data))
        self._sequence_id = sequence_id

    async def _replace_sequence(self, sequence_id: str, data: str) -> None:
        """In case a sequence is already loaded or is executing, abort the task and remove the sequence before retrying."""
        await asyncio.gather(
            self._client.abort_all_tasks(),
            self._client.delete_all_sequences(),
            self._client.load_sequence(sequence_id, data),
        )

    def run(self) -> None:
        """Start a task to run the sequence loaded by :meth:`send`.

        Returns once the device has started the task.

        Raises:
            DeviceError: if :meth:`send` loaded no sequence since the last run.
            RPCResponseError: if the device did not start the task, e.g. as its sequence
                was removed meanwhile.
            TimeoutError: if the device did not answer the start. The task is aborted in
                case the device starts it late.
        """
        sequence_id, self._sequence_id = self._sequence_id, None
        if sequence_id is None:
            raise DeviceError(f"no sequence was loaded on {self.display_name}")
        self._task = self._sync.run(ExperimentTask.start(self._client, sequence_id))

    def receive(self) -> Readouts:
        """Wait for the task started by :meth:`run` to finish and return its results.

        Raises:
            TimeoutError: if the task did not finish within the task timeout of its
                sequence, counted from this call. The task was aborted.
            TaskAbortedError: if the task was aborted meanwhile, e.g. by another client or
                by the device on an error. The error log of the device is logged.
            DeviceError: if no task was started.
            ConnectionError: if the connection was lost before the task ended. The device
                aborts the task then.
        """
        task, self._task = self._task, None
        if task is None:
            raise DeviceError(f"no task was started on {self.display_name}")
        try:
            end = self._sync.run(asyncio.wait_for(task, self._task_timeout))
        except TimeoutError as e:
            raise TimeoutError(
                f"Task on {self.display_name} did not finish within "
                f"{self._task_timeout:g}s and was aborted"
            ) from e
        except TaskAbortedError as e:
            self._log_task_log(e.end.result)
            raise
        self._log_task_log(end.result)
        # TODO: return the per-shot results once ICON handles them
        return to_zedboard_readouts(end.result, self._channel_layout)

    def _log_task_log(self, result: TaskResult) -> None:
        """Log the errors the device reports for a task, e.g. of failed shots."""
        if result.log:
            logger.warning("%s: %s", self.display_name, result.log)


_HEADER_MARKER = '"header":'


def _decode_header(sequence_json: str) -> dict[str, Any]:
    """Partially decode the header out of the sequence, falling back to a full decode."""
    try:
        start = sequence_json.index(_HEADER_MARKER) + len(_HEADER_MARKER)
        return json.JSONDecoder().raw_decode(sequence_json, start)[0]
    except ValueError:
        logger.warning(
            "Sequence description format unexpected. Expecting dense format with no spaces. Falling back to slow decoder."
        )
    try:
        return json.loads(sequence_json).get("header", {})
    except ValueError as e:
        raise DeviceError("Submitted sequence is not valid JSON. Can't run") from e


def _shots_time(header: dict[str, Any]) -> float:
    """Seconds all shots of the sequence take, as given in its header.

    Zero for sequences generated without their time.
    """
    return header.get("shots", 1) * header.get("sequence_max_time_ns", 0) * 1e-9


# *** Zedboard compatibility
#
# Qendra Pulse returns the raw values per data channel and shot, and leaves the
# post-processing to the client. The following reproduces the readouts of the Zedboard
# sequence runner from them, so ICON handles Qendra Pulse data like Zedboard data.
#
# Shot, readout and vector channels are separate namespaces, so Qendra Pulse prefixes the
# channel names with "shot/", "readout/" and "vector/". The readouts drop the prefixes.
#
# TODO: Remove once ICON handles the per-shot results of the device.


class PostProcessing(IntEnum):
    """Readout post-processing method, as given in the sequence header."""

    NONE = 0
    AVG = 1
    SUM = 2
    VECT = 3


@dataclass(frozen=True)
class ChannelLayout:
    """Data channels of a sequence, as declared in its header."""

    readout_channels: list[str] = field(default_factory=list)
    shot_channels: list[str] = field(default_factory=list)
    vector_channels: list[str] = field(default_factory=list)
    postprocessing: list[int] = field(default_factory=list)
    """:class:`PostProcessing` method per readout channel."""

    @classmethod
    def from_header(cls, header: dict[str, Any], *, device_id: str | None) -> Self:
        """Read the channel layout from the header of the sequence.

        Like on the Zedboard, the layout is empty unless the device reads out the sequence.
        """
        readout_hardware = (header.get("channel_idx_to_hw") or [{}])[0]
        if (
            readout_hardware.get("device") != device_id
            or readout_hardware.get("hardware") != "Readout"
        ):
            return cls()
        return cls(
            readout_channels=header.get("readout_channel_names", []),
            shot_channels=header.get("shot_channel_names", []),
            vector_channels=header.get("vector_channel_names", []),
            postprocessing=header.get("readout_postprocessing_method", []),
        )


def to_zedboard_readouts(result: TaskResult, layout: ChannelLayout) -> Readouts:
    """Reduce the per-shot results to the readouts of the Zedboard sequence runner.

    Readout channels are reduced by their post-processing method: AVG to the mean over
    the shots and SUM to the sum, both as result channel, and VECT to a vector channel.
    Shot and vector channels hold the values of all shots in turn.
    """
    shot_channels = {
        name: [int(value) for value in _all_shots(result, f"shot/{name}")]
        for name in layout.shot_channels
    }
    vector_channels = {
        name: _all_shots(result, f"vector/{name}") for name in layout.vector_channels
    }
    result_channels: dict[str, float] = {}
    for name, method in zip(
        layout.readout_channels, layout.postprocessing, strict=False
    ):
        values = _all_shots(result, f"readout/{name}")
        match method:
            case PostProcessing.AVG:
                # The Zedboard averages over the number of shots
                shots = len(result.data.get(f"readout/{name}", []))
                result_channels[name] = sum(values) / max(shots, 1)
            case PostProcessing.SUM:
                result_channels[name] = float(sum(values))
            case PostProcessing.VECT:
                vector_channels[name] = values
    return Readouts(
        result_channels=result_channels,
        vector_channels=vector_channels,
        shot_channels=shot_channels,
    )


def _all_shots(result: TaskResult, channel: str) -> list[float]:
    """Values of ``channel`` of all shots in turn."""
    return [value for shot in result.data.get(channel, []) for value in shot]
