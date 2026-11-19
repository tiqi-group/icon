from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import threading
import weakref
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Final, Self, TypeVar

from qendra.device_client import (
    ApiVersionError,
    DeviceClient,
    DeviceError,
    PulseClient,
    RPCError,
    RPCResponseError,
    TaskStatus,
    UpdateState,
)
from qendra.device_client.config import DEFAULT_CALL_TIMEOUT

from icon.server.data_access.experiment_data import Readouts
from icon.server.hardware_processing.hardware_controller import (
    HardwareController,
    StatusFlag,
)

if TYPE_CHECKING:
    import concurrent.futures
    from collections.abc import Coroutine

    from qendra.device_client import TaskResult

logger = logging.getLogger(__name__)

T = TypeVar("T")

CLIENT_NAME: Final = f"ICON@{socket.gethostname()}"
"""Client name of the sessions ICON registers on the devices."""

SEQUENCE_TIME_FACTOR: Final = 1.5
"""Factor on the time the shots of a task take, to allow for the overhead per shot."""


# *** Event loop
#
# The device clients are asyncio, while the Hardware Controllers are called from the
# threads of the hardware worker and the status checks. The clients of a process therefore
# all run on one event loop on a daemon thread, which the controllers hand their calls to.

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _event_loop() -> asyncio.AbstractEventLoop:
    """Event loop of the device clients of this process, started on first use."""
    global _loop  # noqa: PLW0603
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(
                target=_loop.run_forever, name="device-clients", daemon=True
            ).start()
        return _loop


def _forget_event_loop() -> None:
    """A forked process has no thread running the loop of its parent, so starts its own."""
    global _loop, _loop_lock  # noqa: PLW0603
    _loop = None
    _loop_lock = threading.Lock()


if hasattr(os, "register_at_fork"):  # POSIX only
    os.register_at_fork(after_in_child=_forget_event_loop)


def _submit(coroutine: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
    """Run ``coroutine`` on the event loop of the device clients."""
    return asyncio.run_coroutine_threadsafe(coroutine, _event_loop())


def _call(coroutine: Coroutine[Any, Any, T]) -> T:
    """Run ``coroutine`` on the event loop of the device clients and return its result.

    Bounded by the timeouts of the calls it makes.
    """
    return _submit(coroutine).result()


def _disconnect_soon(client: DeviceClient) -> None:
    """Close the connection of a device client that is no longer used.

    The receiver task of the client keeps the client and its connection alive.
    """
    loop = _loop
    if loop is not None and loop.is_running():
        asyncio.run_coroutine_threadsafe(client.disconnect(), loop)


class RFSoCController(HardwareController):
    """Qendra Pulse (ZCU216 RFSoC) Hardware Controller using the experiment API of the device.

    A sequence runs as a task: :meth:`send` sets it up, :meth:`run` starts it and
    :meth:`receive` waits for it to finish and collects its results. The device stays
    responsive while the task runs, so it can be aborted.

    The client runs on the event loop shared by the device clients of the process. The
    connection is closed when the controller is dropped.
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
        weakref.finalize(self, _disconnect_soon, self._client)
        self._task_timeout_margin = task_timeout_margin
        self._task_timeout = task_timeout_margin
        self._task: concurrent.futures.Future[None] | None = None
        """The wait of :meth:`run` for the task to finish, which :meth:`receive` takes."""
        self._device_id: str | None = None
        self._channel_layout = ChannelLayout()

    # *** Connection

    def connect(self) -> None:
        _call(self._connect())

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
            health = _call(self._client.get_health())
        except (RPCError, OSError) as e:
            return (StatusFlag.UNKNOWN, str(e), None)
        return (StatusFlag.SUCCESS, "OK", health)

    # *** Task

    def send(self, data: str) -> None:
        """Set up the task of the sequence ``data``.

        If that fails while a task left over from an earlier data point is still active,
        the leftover task is aborted and the setup repeated.
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
        try:
            _call(self._client.setup_task(data))
        except RPCResponseError:
            if _call(self._client.get_task_status()).status is TaskStatus.IDLE:
                raise
            logger.warning("Aborting a leftover task on %s", self.display_name)
            _call(self._client.abort_task())
            _call(self._client.setup_task(data))

    def run(self) -> None:
        """Start the task set up by :meth:`send`, which runs on while :meth:`receive` waits.

        The task is aborted if it does not finish within the task timeout of its sequence.
        """
        self._task = _submit(self._client.start_task(timeout=self._task_timeout))

    def receive(self) -> Readouts:
        """Wait for the task started by :meth:`run` to finish and collect its results.

        Raises:
            TimeoutError: if the task did not finish within the task timeout of its
                sequence. The task was aborted.
            DeviceError: if no task was started, or the task was aborted meanwhile.
            ConnectionError: if the connection was lost before the task ended. The next
                :meth:`send` aborts the task if it is still active.
        """
        task, self._task = self._task, None
        if task is None:
            raise DeviceError(f"no task was started on {self.display_name}")
        try:
            task.result()
        except TimeoutError as e:
            if e.args:
                # A call timed out, which its message names
                raise
            # start_task raises a bare TimeoutError once its timeout has expired
            raise TimeoutError(
                f"Task on {self.display_name} did not finish within "
                f"{self._task_timeout:g}s and was aborted"
            ) from e
        results = _call(self._client.get_task_results())
        if results.log:
            logger.warning("%s: %s", self.display_name, results.log)
        # TODO: return the per-shot results once ICON handles them
        return to_zedboard_readouts(results, self._channel_layout)


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
