"""Tests for the RFSoC controller against a fake gateway."""

from __future__ import annotations

import contextlib
import json
import select
import socket
import threading
import time
from typing import TYPE_CHECKING, Any

import msgpack
import pytest

from icon.server.data_access.experiment_data import Readouts
from icon.server.hardware_processing.gateway_controller import CLIENT_NAME
from icon.server.hardware_processing.rfsoc_controller import (
    ChannelLayout,
    RFSoCController,
    _decode_header,
    to_zedboard_readouts,
)
from icon.server.hardware_processing.rpc.gateway import (
    DeviceInfo,
    GatewayError,
    Session,
    TaskNotification,
    TaskResult,
    TaskStatus,
    TaskStatusReport,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

DEVICE_ID = "rfsoc"

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


class FakeGateway:
    """Unframed msgpack-rpc server with the task state machine of the firmware."""

    def __init__(self) -> None:
        self.status = TaskStatus.IDLE
        self.update_state = "none"
        self.sessions_supported = True
        self.sessions: list[str] = []
        self.task_duration: float | None = 0
        """Seconds a started task runs, ``None`` to run until aborted."""
        self.task_end: TaskNotification | None = TaskNotification.FINISHED
        """Notification that ends a task: FINISHED, ABORTED by another client, or
        ``None`` for a finished task whose notification the client misses."""
        self.hang_on: str | None = None
        """Method the device locks up on, never answering it."""
        self.methods: list[str] = []
        self._notifications: list[str] = []
        self._task_start = 0.0
        self._closed = False
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

    def _run(self, conn: socket.socket) -> None:
        """Like the firmware main loop: notify, process requests and run the task."""
        unpacker = msgpack.Unpacker(raw=False)
        while not self._closed:
            for notification in self._notifications:
                conn.sendall(_pack([2, "exp.TaskNotification", [notification]]))
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
            if self.task_end is not None:
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
            case "sys.RegisterSession" if self.sessions_supported:
                self.sessions.append(params[0])
            case "sys.ListSessions" if self.sessions_supported:
                return [[name, "127.0.0.1", 50000] for name in self.sessions]
            case "sys.GetDeviceInfo":
                return DEVICE_INFO
            case "sys.CheckUpdate":
                return self.update_state
            case "sys.ConfirmUpdate":
                self.update_state = params[0]
            case "exp.GetDeviceID":
                return DEVICE_ID
            case "exp.AbortTask":
                self.status = TaskStatus.IDLE
                self._notifications.append(TaskNotification.ABORTED.value)
            case "exp.SetupTask":
                self._require(TaskStatus.IDLE)
                self.status = TaskStatus.SETUP
            case "exp.StartTask":
                self._require(TaskStatus.SETUP)
                self.status = TaskStatus.RUNNING
                self._task_start = time.monotonic()
            case "exp.GetTaskStatus":
                return f"Status {self.status}, executed 0 / 2 shots in 0 ms\n"
            case "exp.GetTaskResults":
                self._require(TaskStatus.FINISHED)
                self.status = TaskStatus.IDLE
                return [DATA, {name: [] for name in DATA}, ""]
            case "exp.RunTask":
                self._require(TaskStatus.IDLE)
                return [DATA, {name: [] for name in DATA}, ""]
            case _:
                raise RuntimeError(f"Invalid request: {method}")
        return None


@pytest.fixture
def gateway() -> Iterator[FakeGateway]:
    fake = FakeGateway()
    yield fake
    fake.close()


def make_controller(
    gateway: FakeGateway,
    poll_interval: float = 1,
    task_timeout_margin: float = 5,
    timeout: float = 2,
    blocking_runtime_limit: float = 1,
) -> RFSoCController:
    return RFSoCController(
        host="127.0.0.1",
        port=gateway.port,
        timeout=timeout,
        poll_interval=poll_interval,
        task_timeout_margin=task_timeout_margin,
        blocking_runtime_limit=blocking_runtime_limit,
    )


@pytest.fixture
def controller(gateway: FakeGateway) -> RFSoCController:
    return make_controller(gateway)


def test_task_round_trip(gateway: FakeGateway, controller: RFSoCController) -> None:
    controller.connect()
    assert controller.query_device_id() == DEVICE_ID

    controller.send(SEQUENCE)
    controller.run()
    readouts = controller.receive()

    assert readouts == EXPECTED
    assert gateway.status is TaskStatus.IDLE
    # Waited on the notification alone, and consumed it
    assert "exp.GetTaskStatus" not in gateway.methods
    assert controller._gateway._client.consume_notifications() == []


def test_connect_confirms_trial_firmware(
    gateway: FakeGateway, controller: RFSoCController
) -> None:
    gateway.update_state = "trial"
    controller.connect()
    assert gateway.update_state == "done"


def test_connect_registers_session(
    gateway: FakeGateway, controller: RFSoCController
) -> None:
    controller.connect()
    assert gateway.sessions == [CLIENT_NAME]
    assert controller._gateway.list_sessions() == [
        Session(client_name=CLIENT_NAME, client_ip="127.0.0.1", client_port=50000)
    ]


def test_connect_without_session_api(
    gateway: FakeGateway, controller: RFSoCController
) -> None:
    gateway.sessions_supported = False
    controller.connect()
    assert controller.connected
    assert controller.query_device_id() == DEVICE_ID


def test_get_device_info(controller: RFSoCController) -> None:
    controller.connect()
    info = controller._gateway.get_device_info()
    assert info.board_model == "ZCU216"
    assert info.submodule_versions == {"pulseway": "f2384fa", "quench_rf": "eac2404"}


@pytest.mark.parametrize(
    "info", [{}, {**DEVICE_INFO, "submodule_versions": None}, "ZCU216"]
)
def test_parse_unexpected_device_info(info: Any) -> None:
    with pytest.raises(GatewayError):
        DeviceInfo.parse(info)


@pytest.mark.parametrize(
    "status", [TaskStatus.SETUP, TaskStatus.RUNNING, TaskStatus.FINISHED]
)
def test_send_aborts_leftover_task(
    gateway: FakeGateway, controller: RFSoCController, status: TaskStatus
) -> None:
    gateway.status = status
    gateway.task_duration = None
    controller.connect()
    controller.send(SEQUENCE)
    assert gateway.status is TaskStatus.SETUP
    assert gateway.methods[-2:] == ["exp.AbortTask", "exp.SetupTask"]


def test_receive_ignores_notification_of_leftover_task(
    gateway: FakeGateway, controller: RFSoCController
) -> None:
    gateway.status = TaskStatus.RUNNING
    gateway.task_duration = None
    controller.connect()
    # Aborting the leftover task notifies ABORTED
    controller.send(SEQUENCE)
    gateway.task_duration = 0
    controller.run()
    assert controller.receive() == EXPECTED


def test_receive_polls_on_missed_notification(gateway: FakeGateway) -> None:
    gateway.task_end = None
    controller = make_controller(gateway, poll_interval=0.05)
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    assert controller.receive() == EXPECTED
    assert gateway.methods.count("exp.GetTaskStatus") == 1
    # The timed out wait left the connection open
    assert controller.connected


def test_receive_aborts_unfinished_task(gateway: FakeGateway) -> None:
    gateway.task_duration = None
    controller = make_controller(gateway, poll_interval=0.02, task_timeout_margin=0.1)
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    start = time.monotonic()
    with pytest.raises(TimeoutError, match=r"did not finish within 0\.1s"):
        controller.receive()
    assert time.monotonic() - start >= 0.1  # noqa: PLR2004
    assert gateway.status is TaskStatus.IDLE
    assert gateway.methods.count("exp.GetTaskStatus") > 1
    assert gateway.methods[-1] == "exp.AbortTask"


def test_task_timeout_covers_the_shots(gateway: FakeGateway) -> None:
    # Takes longer than the margin, but not than 1.5 times the shots (0.3s)
    gateway.task_duration = 0.2
    gateway.task_end = None
    controller = make_controller(
        gateway, poll_interval=0.02, task_timeout_margin=0.05, blocking_runtime_limit=0
    )
    controller.connect()
    controller.send(make_sequence(shots=2, sequence_max_time_ns=100e6))
    controller.run()
    assert controller.receive() == EXPECTED


def test_task_timeout_of_the_sequence(gateway: FakeGateway) -> None:
    gateway.task_duration = None
    controller = make_controller(
        gateway, poll_interval=0.02, task_timeout_margin=0.05, blocking_runtime_limit=0
    )
    controller.connect()
    controller.send(make_sequence(shots=2, sequence_max_time_ns=10e6))
    controller.run()
    # The margin and 1.5 times the shots
    with pytest.raises(TimeoutError, match=r"did not finish within 0\.08s"):
        controller.receive()


def test_receive_fails_on_task_aborted_by_other_client(
    gateway: FakeGateway, controller: RFSoCController
) -> None:
    gateway.task_end = TaskNotification.ABORTED
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    with pytest.raises(GatewayError, match="aborted"):
        controller.receive()
    assert controller.connected


def test_call_timeout_names_the_call(gateway: FakeGateway) -> None:
    gateway.hang_on = "exp.StartTask"
    controller = make_controller(gateway, timeout=0.1)
    controller.connect()
    controller.send(SEQUENCE)
    with pytest.raises(
        TimeoutError, match=r"^no response to exp\.StartTask within 0\.1s$"
    ):
        controller.run()
    # The answer may still arrive, so the connection is dropped
    assert not controller.connected


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


def test_short_task_runs_with_one_call(
    gateway: FakeGateway, controller: RFSoCController
) -> None:
    controller.connect()
    controller.send(make_sequence(shots=2, sequence_max_time_ns=1e6))
    controller.run()

    assert controller.receive() == EXPECTED
    assert "exp.RunTask" in gateway.methods
    assert not {"exp.SetupTask", "exp.StartTask"} & set(gateway.methods)


@pytest.mark.parametrize(
    ("header", "blocking_runtime_limit"),
    [
        ({}, 1),  # A sequence without its time
        ({"shots": 2, "sequence_max_time_ns": 0.5e9}, 1),  # Shots of 1 s
        ({"shots": 2, "sequence_max_time_ns": 1e6}, 0),  # Blocking runs disabled
    ],
)
def test_task_runs_in_steps(
    gateway: FakeGateway, header: dict[str, Any], blocking_runtime_limit: float
) -> None:
    controller = make_controller(gateway, blocking_runtime_limit=blocking_runtime_limit)
    controller.connect()
    controller.send(make_sequence(**header))
    controller.run()

    assert controller.receive() == EXPECTED
    assert "exp.SetupTask" in gateway.methods
    assert "exp.RunTask" not in gateway.methods


def test_short_task_aborts_leftover_task(
    gateway: FakeGateway, controller: RFSoCController
) -> None:
    gateway.status = TaskStatus.RUNNING
    gateway.task_duration = None
    controller.connect()
    controller.send(make_sequence(sequence_max_time_ns=1e6))
    controller.run()

    assert controller.receive() == EXPECTED
    assert gateway.methods[-3:] == ["exp.GetTaskStatus", "exp.AbortTask", "exp.RunTask"]
