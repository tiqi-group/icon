"""Tests for the RFSoC (Qendra Pulse) controller against a fake device."""

from __future__ import annotations

import contextlib
import dataclasses
import gc
import json
import select
import socket
import threading
import time
from typing import TYPE_CHECKING, Any

import msgpack
import pytest
from qendra.device_client import (
    DeviceError,
    DeviceInfo,
    NotificationTopic,
    PulseClient,
    Session,
    TaskNotification,
    TaskResult,
    TaskStatus,
    TaskStatusReport,
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


class FakeDevice:
    """Unframed msgpack-rpc server with the task state machine of the firmware."""

    def __init__(self) -> None:
        assert PulseClient.API_VERSION is not None
        self.api_version = dataclasses.asdict(PulseClient.API_VERSION)
        """Interface version the firmware reports, the one the client implements."""
        self.status = TaskStatus.IDLE
        self.update_state = "none"
        self.sessions_supported = True
        self.sessions: list[str] = []
        self.task_duration: float | None = 0
        """Seconds a started task runs, ``None`` to run until aborted."""
        self.task_end = TaskNotification.FINISHED
        """Notification that ends a task: FINISHED, or ABORTED by another client."""
        self.hang_on: str | None = None
        """Method the device locks up on, never answering it."""
        self.methods: list[str] = []
        self._notifications: list[str] = []
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

    def _run(self, conn: socket.socket) -> None:
        """Like the firmware main loop: notify, process requests and run the task."""
        unpacker = msgpack.Unpacker(raw=False)
        while not self._closed:
            for notification in self._notifications:
                conn.sendall(_pack([2, NotificationTopic.TASK.value, [notification]]))
            self._notifications.clear()
            readable, _, _ = select.select([conn], [], [], 0.001)
            if readable:
                chunk = conn.recv(65536)
                if not chunk:
                    return
                unpacker.feed(chunk)
                for _, msgid, method, params in unpacker:
                    self.methods.append(method)
                    if method != self.hang_on:
                        conn.sendall(self._respond(msgid, method, params))
            self._work()

    def _work(self) -> None:
        """End the running task once its duration has passed."""
        if (
            self.status is TaskStatus.RUNNING
            and self.task_duration is not None
            and time.monotonic() - self._task_start >= self.task_duration
        ):
            aborted = self.task_end is TaskNotification.ABORTED
            self.status = TaskStatus.IDLE if aborted else TaskStatus.FINISHED
            self._notifications.append(self.task_end.value)

    def _respond(self, msgid: int, method: str, params: list[Any]) -> bytes:
        try:
            response = [1, msgid, None, self._handle(method, params)]
        except RuntimeError as e:
            response = [1, msgid, str(e), None]
        return _pack(response)

    def _require(self, status: TaskStatus) -> None:
        if self.status is not status:
            raise RuntimeError(f"Current task is not {status}; Status {self.status}")

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
                self.update_state = params[0]
            case "exp.getDeviceID":
                return DEVICE_ID
            case "exp.abortTask":
                self.status = TaskStatus.IDLE
                self._notifications.append(TaskNotification.ABORTED.value)
            case "exp.setupTask":
                self._require(TaskStatus.IDLE)
                self.status = TaskStatus.SETUP
            case "exp.startTask":
                self._require(TaskStatus.SETUP)
                self.status = TaskStatus.RUNNING
                self._task_start = time.monotonic()
            case "exp.getTaskStatus":
                return f"Status {self.status}, executed 0 / 2 shots in 0 ms\n"
            case "exp.getTaskResults":
                self._require(TaskStatus.FINISHED)
                self.status = TaskStatus.IDLE
                return [DATA, {name: [] for name in DATA}, ""]
            case "exp.runTask":
                self._require(TaskStatus.IDLE)
                return [DATA, {name: [] for name in DATA}, ""]
            case _:
                raise RuntimeError(f"Invalid request: {method}")
        return None


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
    assert device.status is TaskStatus.IDLE
    # Never blocks the device with exp.runTask, and waits on the notification alone
    assert device.methods[-3:] == [
        "exp.setupTask",
        "exp.startTask",
        "exp.getTaskResults",
    ]
    assert "exp.getTaskStatus" not in device.methods


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


@pytest.mark.parametrize(
    "status", [TaskStatus.SETUP, TaskStatus.RUNNING, TaskStatus.FINISHED]
)
def test_send_aborts_leftover_task(
    device: FakeDevice, controller: RFSoCController, status: TaskStatus
) -> None:
    device.status = status
    device.task_duration = None
    controller.connect()
    controller.send(SEQUENCE)
    assert device.status is TaskStatus.SETUP
    assert device.methods[-2:] == ["exp.abortTask", "exp.setupTask"]


def test_receive_ignores_notification_of_leftover_task(
    device: FakeDevice, controller: RFSoCController
) -> None:
    device.status = TaskStatus.RUNNING
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
    assert device.status is TaskStatus.IDLE
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


def test_receive_fails_on_task_aborted_by_other_client(
    device: FakeDevice, controller: RFSoCController
) -> None:
    device.task_end = TaskNotification.ABORTED
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    with pytest.raises(DeviceError, match="aborted"):
        controller.receive()
    assert controller.connected


def test_call_timeout_names_the_call(device: FakeDevice) -> None:
    device.hang_on = "exp.startTask"
    controller = make_controller(device, timeout=0.1)
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    with pytest.raises(
        TimeoutError,
        match=r"^no response to exp\.startTask \(msgid \d+\) within 0\.1s$",
    ):
        controller.receive()
    # The late answer is dropped, so the connection stays open
    assert controller.connected
    # The device never confirmed the start, so nothing is aborted: the next send aborts
    # the task if it is still active
    assert device.methods[-1] == "exp.startTask"


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


def test_parse_task_status() -> None:
    report = TaskStatusReport.parse("Status RUNNING, executed 3 / 10 shots in -5 ms\n")
    assert report == TaskStatusReport(
        status=TaskStatus.RUNNING,
        executed_shots=3,
        requested_shots=10,
        duration_ms=-5,
    )
