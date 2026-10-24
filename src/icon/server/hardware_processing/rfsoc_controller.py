from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Final, Self, TypeVar

from icon.server.data_access.experiment_data import Readouts
from icon.server.hardware_processing.gateway_controller import GatewayController
from icon.server.hardware_processing.rpc.errors import RPCError, RPCResponseError
from icon.server.hardware_processing.rpc.gateway import (
    GatewayError,
    RFSoC,
    TaskStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from icon.server.hardware_processing.rpc.gateway import TaskResult

logger = logging.getLogger(__name__)

T = TypeVar("T")

SEQUENCE_TIME_FACTOR: Final = 1.5
"""Factor on the time the shots of a task take, to allow for the overhead per shot."""


class RFSoCController(GatewayController[RFSoC]):
    """RFSoC (ZCU216) Hardware Controller using the experiment API of the gateway.

    A sequence runs as a task: :meth:`send` sets it up, :meth:`run` starts it and
    :meth:`receive` waits for it to finish and collects its results. A short task instead
    runs with a single blocking ``exp.RunTask`` call in :meth:`receive`, which saves the
    round trips, but leaves the device unable to answer other requests (like an abort)
    while the task runs.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        timeout: float = 5,
        poll_interval: float = 1,
        task_timeout_margin: float = 5,
        blocking_runtime_limit: float = 1,
    ) -> None:
        """Initialise the controller.

        Args:
            host: Hostname of the RFSoC.
            port: Port the RFSoC RPC server listens on.
            timeout: Timeout in seconds for RPC calls.
            poll_interval: Seconds to wait for the notification that the task has
                finished, before polling the task status.
            task_timeout_margin: Seconds to wait for a task on top of
                :data:`SEQUENCE_TIME_FACTOR` times the time its shots take, before
                aborting it.
            blocking_runtime_limit: Tasks whose shots take less than this many seconds
                run with a single blocking call. Sequences without their time always
                run in steps. 0 disables blocking runs.
        """
        super().__init__(RFSoC(hostname=host, port=port, timeout=timeout))
        self._poll_interval = poll_interval
        self._task_timeout_margin = task_timeout_margin
        self._task_timeout = task_timeout_margin
        self._blocking_runtime_limit = blocking_runtime_limit
        self._blocking = False
        self._sequence = ""
        self._device_id: str | None = None
        self._channel_layout = ChannelLayout()

    def connect(self) -> None:
        super().connect()
        if not self.connected:
            return
        try:
            self._device_id = self._gateway.get_device_id()
        except (RPCError, OSError) as e:
            logger.warning(
                "Could not query the device id of %s: %s", self.display_name, e
            )

    def query_device_id(self) -> str | None:
        return self._device_id

    def send(self, data: str) -> None:
        self._ensure_connected()
        header = _decode_header(data)
        shots_time = _shots_time(header)
        self._task_timeout = (
            self._task_timeout_margin + SEQUENCE_TIME_FACTOR * shots_time
        )
        # TODO: drop together with the Zedboard compatibility
        self._channel_layout = ChannelLayout.from_header(
            header, device_id=self._device_id
        )
        # A sequence without its time may run for any time
        self._blocking = 0 < shots_time < self._blocking_runtime_limit
        if self._blocking:
            # Sent with the call that runs it in receive
            self._sequence = data
            return
        self._call_aborting_leftover_task(lambda: self._gateway.setup_task(data))

    def run(self) -> None:
        if self._blocking:
            return
        self._gateway.start_task()

    def receive(self) -> Readouts:
        if self._blocking:
            # A task left running by a call that timed out is aborted by the next call
            results = self._call_aborting_leftover_task(
                lambda: self._gateway.run_task(
                    self._sequence, timeout=self._task_timeout
                )
            )
        else:
            self._wait_for_task()
            results = self._gateway.get_task_results()
        if results.log:
            logger.warning("%s: %s", self.display_name, results.log)
        # TODO: return the per-shot results once ICON handles them
        return to_zedboard_readouts(results, self._channel_layout)

    def _call_aborting_leftover_task(self, call: Callable[[], T]) -> T:
        """Make a call that requires an IDLE task.

        If it fails while a task left over from an earlier data point is still active,
        the leftover task is aborted and the call repeated.
        """
        try:
            return call()
        except RPCResponseError:
            if self._gateway.get_task_status().status is TaskStatus.IDLE:
                raise
            logger.warning("Aborting a leftover task on %s", self.display_name)
            self._gateway.abort_task()
            return call()

    def _wait_for_task(self) -> None:
        """Wait for the running task to finish.

        Blocks until the device notifies that the task has finished. As the notification
        can be missed, the task status is polled every poll interval. The task is aborted
        once it is still unfinished after the task timeout of its sequence.

        Raises:
            TimeoutError: if the task did not finish and was aborted.
            GatewayError: if no task is running, or the task was aborted meanwhile.
        """
        deadline = time.monotonic() + self._task_timeout
        while True:
            remaining = max(deadline - time.monotonic(), 0)
            if self._gateway.wait_for_task(timeout=min(self._poll_interval, remaining)):
                return
            report = self._gateway.get_task_status()
            if report.status is TaskStatus.FINISHED:
                return
            if report.status is not TaskStatus.RUNNING:
                raise GatewayError(
                    f"no task is running on {self.display_name}: {report}"
                )
            if time.monotonic() >= deadline:
                break
        logger.warning("Aborting the unfinished task on %s", self.display_name)
        try:
            self._gateway.abort_task()
        except (RPCError, OSError) as e:
            # The next send aborts the task again
            logger.warning("Could not abort the task on %s: %s", self.display_name, e)
        raise TimeoutError(
            f"Task on {self.display_name} did not finish within {self._task_timeout:g}s "
            f"({report.executed_shots} / {report.requested_shots} shots) and was aborted"
        )


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
        raise GatewayError("Submitted sequence is not valid JSON. Can't run") from e


def _shots_time(header: dict[str, Any]) -> float:
    """Seconds all shots of the sequence take, as given in its header.

    Zero for sequences generated without their time.
    """
    return header.get("shots", 1) * header.get("sequence_max_time_ns", 0) * 1e-9


# *** Zedboard compatibility
#
# The RFSoC returns the raw values per data channel and shot, and leaves the
# post-processing to the client. The following reproduces the readouts of the Zedboard
# sequence runner from them, so ICON handles RFSoC data like Zedboard data.
#
# Shot, readout and vector channels are separate namespaces, so the RFSoC prefixes the
# channel names with "shot/", "readout/" and "vector/". The readouts drop the prefixes.
#
# TODO: Remove once ICON handles the per-shot results of the gateway.


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
