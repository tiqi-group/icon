"""Tests for the RFSoC (Qendra Pulse) controller against a fake device."""

from __future__ import annotations

import contextlib
import dataclasses
import gc
import hashlib
import json
import select
import socket
import threading
import time
from enum import Enum
from typing import TYPE_CHECKING, Any

import msgpack
import pytest
from qendra.device_client import (
    DeviceError,
    DeviceInfo,
    NotificationTopic,
    PulseClient,
    RPCResponseError,
    Session,
    TaskAbortedError,
    TaskResult,
    TaskStatus,
)

from icon.server.data_access.experiment_data import Readouts
from icon.server.hardware_processing.hardware_controller import StatusFlag
from icon.server.hardware_processing.rfsoc_controller import (
    CLIENT_NAME,
    ChannelLayout,
    RFSoCController,
    _decode_header,
    to_zedboard_readouts,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

DEVICE_ID = "rfsoc"

HEALTH = {"cpu_temperature": 45.0, "clk_status": "external"}

DEVICE_INFO = {
    "board_model": "ZCU216",
    "board_serial_number": "1234",
    "board_mac_address": "00:0a:35:00:00:01",
    "firmware_build": "Oct 22 2026 13:24:03",
    "firmware_version": "1.0.0",
    "gateware_version": "1.0.0",
    "submodule_versions": [["pulseway", "f2384fa"], ["quench_rf", "eac2404"]],
}

HEADER = {
    "channel_idx_to_hw": [{"device": DEVICE_ID, "hardware": "Readout"}],
    "shot_channel_names": ["pmt"],
    # The readout channel "pmt" shares its name with the shot channel
    "readout_channel_names": ["bright", "pmt", "trace", "ignored"],
    "readout_postprocessing_method": [1, 2, 3, 0],
    "vector_channel_names": ["timestamps"],
}


def make_sequence(**header: Any) -> str:
    """Sequence with ``header`` added to :data:`HEADER`."""
    return json.dumps(
        {"header": {**HEADER, **header}, "sequences": []}, separators=(",", ":")
    )


SEQUENCE = make_sequence()

DATA = {
    "shot/pmt": [[3.0], [5.0]],
    "readout/bright": [[1.0], [0.0]],
    "readout/pmt": [[2.0], [4.0]],
    "readout/trace": [[1.0], [0.0]],
    "readout/ignored": [[7.0], [7.0]],
    "vector/timestamps": [[1.0, 2.0], [3.0]],
}

EXPECTED = Readouts(
    result_channels={"bright": 0.5, "pmt": 6.0},
    vector_channels={"timestamps": [1.0, 2.0, 3.0], "trace": [1.0, 0.0]},
    shot_channels={"pmt": [3, 5]},
)


def _pack(obj: Any) -> bytes:
    packed = msgpack.packb(obj)
    assert packed is not None
    return packed


class Slot(Enum):
    """State of the sequence slot of the firmware."""

    IDLE = "IDLE"
    """No sequence loaded."""
    SETUP = "SETUP"
    """A sequence is loaded, waiting to run."""
    RUNNING = "RUNNING"
    """The task of the loaded sequence runs."""


class FakeDevice:
    """Unframed msgpack-rpc server with the sequence slot and task state machine of the firmware."""

    def __init__(self) -> None:
        assert PulseClient.API_VERSION is not None
        self.api_version = dataclasses.asdict(PulseClient.API_VERSION)
        """Interface version the firmware reports, the one the client implements."""
        self.slot = Slot.IDLE
        self.sequence_id = ""
        """The loaded sequence, unless the slot is IDLE."""
        self.task_id = 0
        """The running task, if the slot is RUNNING."""
        self.update_state = "none"
        self.sessions_supported = True
        self.sessions: list[str] = []
        self.load_error: str | None = None
        """Error exp.loadSequence reports for the sequence itself, e.g. invalid."""
        self.task_duration: float | None = 0
        """Seconds a started task runs, ``None`` to run until aborted."""
        self.task_end = TaskStatus.FINISHED
        """How a task ends: FINISHED, or ABORTED by the device or another client."""
        self.task_log = ""
        """Error log of the device in the results of a task."""
        self.hang_on: str | None = None
        """Method the device locks up on, never answering it."""
        self.methods: list[str] = []
        self._notifications: list[list[Any]] = []
        self._task_start = 0.0
        self._closed = False
        self.disconnected = threading.Event()
        """Set once the client has closed the connection."""
        self._server = socket.create_server(("127.0.0.1", 0))
        self.port: int = self._server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def close(self) -> None:
        self._closed = True
        self._server.close()

    def _serve(self) -> None:
        try:
            conn, _ = self._server.accept()
        except OSError:
            return
        # The client goes away by closing or resetting the connection
        with conn, contextlib.suppress(ConnectionError):
            self._run(conn)
        self.disconnected.set()

    def load(self, sequence_id: str, *, running: bool = False) -> None:
        """Leave a sequence in the slot, as an earlier data point or another client would."""
        self.sequence_id = sequence_id
        self.slot = Slot.RUNNING if running else Slot.SETUP
        self.task_id = 1
        self._task_start = time.monotonic()

    def _run(self, conn: socket.socket) -> None:
        """Like the firmware main loop: notify, process requests and run the task."""
        unpacker = msgpack.Unpacker(raw=False)
        while not self._closed:
            self._notify(conn)
            readable, _, _ = select.select([conn], [], [], 0.001)
            if readable:
                chunk = conn.recv(65536)
                if not chunk:
                    return
                unpacker.feed(chunk)
                for _, msgid, method, params in unpacker:
                    self.methods.append(method)
                    if method != self.hang_on:
                        response = self._respond(msgid, method, params)
                        # The notifications of a request precede its response
                        self._notify(conn)
                        conn.sendall(response)
            self._work()

    def _notify(self, conn: socket.socket) -> None:
        for params in self._notifications:
            conn.sendall(_pack([2, NotificationTopic.TASK.value, params]))
        self._notifications.clear()

    def _work(self) -> None:
        """End the running task once its duration has passed."""
        if (
            self.slot is Slot.RUNNING
            and self.task_duration is not None
            and time.monotonic() - self._task_start >= self.task_duration
        ):
            self._end_task(self.task_end)

    def _end_task(self, status: TaskStatus) -> None:
        """Notify the end of the running task, which unloads its sequence."""
        executed = 2 if status is TaskStatus.FINISHED else 1
        message = f"executed {executed} / 2 shots in 0 ms"
        result = [DATA, {name: [] for name in DATA}, self.task_log]
        self._notifications.append(
            [self.task_id, status.value, {self.sequence_id: [message, result]}]
        )
        self.slot = Slot.IDLE

    def _respond(self, msgid: int, method: str, params: list[Any]) -> bytes:
        try:
            response = [1, msgid, None, self._handle(method, params)]
        except RuntimeError as e:
            response = [1, msgid, str(e), None]
        return _pack(response)

    def _handle(self, method: str, params: list[Any]) -> Any:  # noqa: C901, PLR0911, PLR0912
        match method:
            case "sys.getApiVersion":
                return self.api_version
            case "sys.getHealth":
                return HEALTH
            case "sys.registerSession" if self.sessions_supported:
                self.sessions.append(params[0])
            case "sys.listSessions" if self.sessions_supported:
                return [[name, "127.0.0.1", 50000] for name in self.sessions]
            case "sys.getDeviceInfo":
                return DEVICE_INFO
            case "sys.checkUpdate":
                return self.update_state
            case "sys.confirmUpdate":
                if self.update_state == "trial":
                    self.update_state = "done"
            case "exp.getDeviceID":
                return DEVICE_ID
            case "exp.loadSequence":
                self._load_sequence(*params)
            case "exp.listSequences":
                return [] if self.slot is Slot.IDLE else [self.sequence_id]
            case "exp.deleteSequence" | "exp.deleteAllSequences":
                self._delete_sequence(*params or [self.sequence_id])
            case "exp.startTask":
                self._start_task(*params)
            case "exp.abortTask" | "exp.abortAllTasks":
                if self.slot is Slot.RUNNING and params in ([], [self.task_id]):
                    self._end_task(TaskStatus.ABORTED)
            case "exp.getTaskStatus":
                if self.slot is not Slot.RUNNING:
                    return []
                message = "executed 0 / 2 shots in 0 ms"
                return [[self.task_id, "RUNNING", {self.sequence_id: [message]}]]
            case _:
                raise RuntimeError(f"Invalid request: {method}")
        return None

    def _load_sequence(self, sequence_id: str, sequence: str) -> None:
        assert isinstance(sequence, str)
        if self.slot is not Slot.IDLE:
            raise RuntimeError(
                f"exp_json_parser::loadSequence: cannot load sequence '{sequence_id}', "
                f"the loaded sequence is '{self.sequence_id}' with status {self.slot.value}"
            )
        if self.load_error is not None:
            raise RuntimeError(self.load_error)
        self.sequence_id = sequence_id
        self.slot = Slot.SETUP

    def _delete_sequence(self, sequence_id: str) -> None:
        if self.slot is Slot.IDLE or sequence_id != self.sequence_id:
            return
        if self.slot is not Slot.SETUP:
            raise RuntimeError(
                f"exp_json_parser::deleteSequence: sequence '{sequence_id}' is not SETUP"
            )
        self.slot = Slot.IDLE

    def _start_task(self, task_id: int, sequence_id: str) -> None:
        if self.slot is not Slot.SETUP or sequence_id != self.sequence_id:
            raise RuntimeError(
                f"exp_json_parser::startTask: sequence '{sequence_id}' is not loaded"
            )
        self.task_id = task_id
        self.slot = Slot.RUNNING
        self._task_start = time.monotonic()


@pytest.fixture
def device() -> Iterator[FakeDevice]:
    fake = FakeDevice()
    yield fake
    fake.close()


def make_controller(
    device: FakeDevice, task_timeout_margin: float = 5, timeout: float = 2
) -> RFSoCController:
    return RFSoCController(
        host="127.0.0.1",
        port=device.port,
        timeout=timeout,
        task_timeout_margin=task_timeout_margin,
    )


@pytest.fixture
def controller(device: FakeDevice) -> RFSoCController:
    return make_controller(device)


@pytest.mark.parametrize(
    "sequence",
    [
        SEQUENCE,  # A sequence without its time
        make_sequence(shots=2, sequence_max_time_ns=1e6),  # A short sequence
    ],
)
def test_task_round_trip(
    device: FakeDevice, controller: RFSoCController, sequence: str
) -> None:
    controller.connect()
    assert controller.query_device_id() == DEVICE_ID

    controller.send(sequence)
    controller.run()
    readouts = controller.receive()

    assert readouts == EXPECTED
    # The end of the task unloads its sequence
    assert device.slot is Slot.IDLE
    # Waits on the notification alone, which brings the results
    assert device.methods[-2:] == ["exp.loadSequence", "exp.startTask"]
    assert "exp.getTaskStatus" not in device.methods


def test_sequence_id_is_the_hash_of_the_sequence(
    device: FakeDevice, controller: RFSoCController
) -> None:
    controller.connect()
    # The same sequence on consecutive data points reuses its id
    for sequence in [SEQUENCE, make_sequence(shots=2), SEQUENCE]:
        controller.send(sequence)
        assert device.sequence_id == hashlib.sha256(sequence.encode()).hexdigest()
        controller.run()
        assert controller.receive() == EXPECTED
    # The end of each task freed the slot, so no load failed
    assert "exp.listSequences" not in device.methods


def test_connect_rejects_incompatible_firmware(
    device: FakeDevice,
    controller: RFSoCController,
    caplog: pytest.LogCaptureFixture,
) -> None:
    device.api_version["major"] += 1
    controller.connect()
    assert not controller.connected
    assert controller.query_device_id() is None
    # Neither registers a session nor touches the firmware update
    assert device.methods == ["sys.getApiVersion"]
    assert "incompatible" in caplog.text


def test_status_reports_health(controller: RFSoCController) -> None:
    controller.connect()
    assert controller.status() == (StatusFlag.SUCCESS, "OK", HEALTH)


def test_status_when_disconnected(controller: RFSoCController) -> None:
    flag, message, data = controller.status()
    assert flag is StatusFlag.UNKNOWN
    assert "not connected" in message
    assert data is None


def test_connect_confirms_trial_firmware(
    device: FakeDevice, controller: RFSoCController
) -> None:
    device.update_state = "trial"
    controller.connect()
    assert device.update_state == "done"


def test_connect_registers_session(
    device: FakeDevice, controller: RFSoCController
) -> None:
    controller.connect()
    assert device.sessions == [CLIENT_NAME]
    assert controller._sync.run(controller._client.list_sessions()) == [
        Session(client_name=CLIENT_NAME, client_ip="127.0.0.1", client_port=50000)
    ]


def test_connect_without_session_api(
    device: FakeDevice, controller: RFSoCController
) -> None:
    device.sessions_supported = False
    controller.connect()
    assert controller.connected
    assert controller.query_device_id() == DEVICE_ID


def test_get_device_info(controller: RFSoCController) -> None:
    controller.connect()
    info = controller._sync.run(controller._client.get_device_info())
    assert info.board_model == "ZCU216"
    assert info.submodule_versions == {"pulseway": "f2384fa", "quench_rf": "eac2404"}


@pytest.mark.parametrize(
    "info", [{}, {**DEVICE_INFO, "submodule_versions": None}, "ZCU216"]
)
def test_parse_unexpected_device_info(info: Any) -> None:
    with pytest.raises(DeviceError):
        DeviceInfo.parse(info)


@pytest.mark.parametrize("running", [False, True], ids=["sequence", "task"])
def test_send_removes_leftover(
    device: FakeDevice, controller: RFSoCController, *, running: bool
) -> None:
    device.load("leftover", running=running)
    device.task_duration = None
    controller.connect()
    controller.send(SEQUENCE)
    assert device.slot is Slot.SETUP
    assert device.sequence_id != "leftover"
    assert device.methods[-5:] == [
        "exp.loadSequence",
        "exp.listSequences",
        "exp.abortAllTasks",
        "exp.deleteAllSequences",
        "exp.loadSequence",
    ]


def test_send_replaces_sequence_that_was_not_run(
    device: FakeDevice, controller: RFSoCController
) -> None:
    """The worker runs no device of a data point if sending to one of them failed."""
    controller.connect()
    controller.send(SEQUENCE)
    controller.send(SEQUENCE)
    assert "exp.deleteAllSequences" in device.methods
    controller.run()
    assert controller.receive() == EXPECTED


def test_send_fails_on_rejected_sequence(
    device: FakeDevice, controller: RFSoCController
) -> None:
    device.load_error = "Number of shots set to 0, no experiment will be executed!"
    controller.connect()
    with pytest.raises(RPCResponseError, match="Number of shots set to 0"):
        controller.send(SEQUENCE)
    # Nothing to remove
    assert device.methods[-2:] == ["exp.loadSequence", "exp.listSequences"]
    with pytest.raises(DeviceError, match="no sequence was loaded"):
        controller.run()


def test_receive_ignores_notification_of_leftover_task(
    device: FakeDevice, controller: RFSoCController
) -> None:
    device.load("leftover", running=True)
    device.task_duration = None
    controller.connect()
    # Aborting the leftover task notifies ABORTED
    controller.send(SEQUENCE)
    device.task_duration = 0
    controller.run()
    assert controller.receive() == EXPECTED


def test_receive_aborts_unfinished_task(device: FakeDevice) -> None:
    device.task_duration = None
    controller = make_controller(device, task_timeout_margin=0.1)
    controller.connect()
    controller.send(SEQUENCE)
    start = time.monotonic()
    controller.run()
    with pytest.raises(
        TimeoutError, match=r"did not finish within 0\.1s and was aborted"
    ):
        controller.receive()
    assert time.monotonic() - start >= 0.1  # noqa: PLR2004
    assert device.slot is Slot.IDLE
    assert device.methods[-1] == "exp.abortTask"
    assert controller.connected


def test_task_timeout_covers_the_shots(device: FakeDevice) -> None:
    # Takes longer than the margin, but not than 1.5 times the shots (0.3s)
    device.task_duration = 0.2
    controller = make_controller(device, task_timeout_margin=0.05)
    controller.connect()
    controller.send(make_sequence(shots=2, sequence_max_time_ns=100e6))
    controller.run()
    assert controller.receive() == EXPECTED


def test_task_timeout_of_the_sequence(device: FakeDevice) -> None:
    device.task_duration = None
    controller = make_controller(device, task_timeout_margin=0.05)
    controller.connect()
    controller.send(make_sequence(shots=2, sequence_max_time_ns=10e6))
    controller.run()
    # The margin and 1.5 times the shots
    with pytest.raises(TimeoutError, match=r"did not finish within 0\.08s"):
        controller.receive()


def test_receive_fails_on_aborted_task(
    device: FakeDevice,
    controller: RFSoCController,
    caplog: pytest.LogCaptureFixture,
) -> None:
    device.task_end = TaskStatus.ABORTED
    device.task_log = "Too many hardware faults, failed after 1 / 2 shots"
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    with pytest.raises(TaskAbortedError, match="aborted after 1 / 2 shots"):
        controller.receive()
    assert controller.connected
    # The reason is in the error log of the device
    assert device.task_log in caplog.text


def test_receive_logs_errors_of_finished_task(
    device: FakeDevice,
    controller: RFSoCController,
    caplog: pytest.LogCaptureFixture,
) -> None:
    device.task_log = "Shot 1 failed and was repeated"
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    assert controller.receive() == EXPECTED
    assert device.task_log in caplog.text


def test_call_timeout_names_the_call(device: FakeDevice) -> None:
    device.hang_on = "exp.startTask"
    controller = make_controller(device, timeout=0.1)
    controller.connect()
    controller.send(SEQUENCE)
    with pytest.raises(
        TimeoutError,
        match=r"^no response to exp\.startTask \(msgid \d+\) within 0\.1s$",
    ):
        controller.run()
    # The late answer is dropped, so the connection stays open
    assert controller.connected
    # The device never answered the start, so the client aborts the task in case it starts
    # late; the next send removes the sequence that is still loaded
    assert device.methods[-2:] == ["exp.startTask", "exp.abortTask"]
    device.hang_on = None
    controller.send(SEQUENCE)
    controller.run()
    assert controller.receive() == EXPECTED


def test_run_returns_once_the_task_started(device: FakeDevice) -> None:
    device.task_duration = None
    controller = make_controller(device)
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    # Started, and running while receive waits
    assert device.slot is Slot.RUNNING
    device.task_duration = 0
    assert controller.receive() == EXPECTED


def test_run_fails_if_the_device_does_not_start_the_task(
    device: FakeDevice, controller: RFSoCController
) -> None:
    controller.connect()
    controller.send(SEQUENCE)
    device.slot = Slot.IDLE  # e.g. removed by another client
    with pytest.raises(RPCResponseError, match="is not loaded"):
        controller.run()
    with pytest.raises(DeviceError, match="no task was started"):
        controller.receive()


def test_receive_without_run(controller: RFSoCController) -> None:
    controller.connect()
    controller.send(SEQUENCE)
    with pytest.raises(DeviceError, match="no task was started"):
        controller.receive()


def test_dropped_controller_disconnects(device: FakeDevice) -> None:
    before = set(threading.enumerate())
    controller = make_controller(device)
    loop_threads = set(threading.enumerate()) - before
    assert loop_threads
    controller.connect()
    del controller
    gc.collect()
    assert device.disconnected.wait(timeout=1)
    # The event loop of the controller is shut down as well
    for thread in loop_threads:
        thread.join(timeout=1)
        assert not thread.is_alive()


def test_close_on_the_event_loop_thread(
    device: FakeDevice, controller: RFSoCController
) -> None:
    """The last reference to a controller can go on any thread, also its event loop's."""
    controller.connect()

    async def drop() -> None:
        controller._finalizer()

    # In a thread of its own, so that a deadlock of the event loop fails the test
    dropping = threading.Thread(
        target=controller._sync.run, args=(drop(),), daemon=True
    )
    dropping.start()
    dropping.join(timeout=1)
    assert not dropping.is_alive()
    assert device.disconnected.wait(timeout=1)


def test_query_device_id_when_unreachable() -> None:
    with socket.create_server(("127.0.0.1", 0)) as server:
        port = server.getsockname()[1]
    controller = RFSoCController(host="127.0.0.1", port=port)
    controller.connect()
    assert controller.query_device_id() is None


def test_layout_is_empty_on_other_device() -> None:
    assert ChannelLayout.from_header(HEADER, device_id="other") == ChannelLayout()


def test_decode_header() -> None:
    assert _decode_header(SEQUENCE) == HEADER


def test_decode_header_falls_back_to_full_decode() -> None:
    sparse = json.dumps(json.loads(SEQUENCE), indent=2)
    assert _decode_header(sparse) == HEADER


def test_to_zedboard_readouts() -> None:
    layout = ChannelLayout.from_header(HEADER, device_id=DEVICE_ID)
    result = TaskResult(data=DATA, failed={}, log="")
    assert to_zedboard_readouts(result, layout) == EXPECTED
