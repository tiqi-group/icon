"""Tests for the RFSoC controller against a fake gateway."""

from __future__ import annotations

import json
import socket
import threading
from typing import TYPE_CHECKING, Any

import msgpack
import pytest

from icon.server.data_access.experiment_data import Readouts
from icon.server.hardware_processing.gateway_controller import CLIENT_NAME
from icon.server.hardware_processing.rfsoc_controller import (
    ChannelLayout,
    RFSoCController,
    to_zedboard_readouts,
)
from icon.server.hardware_processing.rpc.gateway import (
    DeviceInfo,
    GatewayError,
    Session,
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

SEQUENCE = json.dumps(
    {
        "header": {
            "channel_idx_to_hw": [{"device": DEVICE_ID, "hardware": "Readout"}],
            "shot_channel_names": ["pmt"],
            "readout_channel_names": ["bright", "count", "trace", "ignored"],
            "readout_postprocessing_method": [1, 2, 3, 0],
            "vector_channel_names": ["timestamps"],
        },
        "sequences": [],
    },
    separators=(",", ":"),
)

DATA = {
    "pmt": [[3.0], [5.0]],
    "bright": [[1.0], [0.0]],
    "count": [[2.0], [4.0]],
    "trace": [[1.0], [0.0]],
    "ignored": [[7.0], [7.0]],
    "timestamps": [[1.0, 2.0], [3.0]],
}

EXPECTED = Readouts(
    result_channels={"bright": 0.5, "count": 6.0},
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
        self.requests_until_finished = 1
        self.methods: list[str] = []
        self._notifications: list[str] = []
        self._server = socket.create_server(("127.0.0.1", 0))
        self.port: int = self._server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def close(self) -> None:
        self._server.close()

    def _serve(self) -> None:
        try:
            conn, _ = self._server.accept()
        except OSError:
            return
        unpacker = msgpack.Unpacker(raw=False)
        with conn:
            while chunk := conn.recv(65536):
                unpacker.feed(chunk)
                for _, msgid, method, params in unpacker:
                    self.methods.append(method)
                    conn.sendall(self._respond(msgid, method, params))

    def _respond(self, msgid: int, method: str, params: list[Any]) -> bytes:
        if self.status is TaskStatus.RUNNING:
            if self.requests_until_finished == 0:
                self.status = TaskStatus.FINISHED
                self._notifications.append("exp::FINISHED")
            self.requests_until_finished -= 1
        # Like the firmware, notify with a nil method ahead of the next response
        notifications = b"".join(_pack([2, None, n]) for n in self._notifications)
        self._notifications.clear()
        try:
            response = [1, msgid, None, self._handle(method, params)]
        except RuntimeError as e:
            response = [1, msgid, str(e), None]
        return notifications + _pack(response)

    def _require(self, status: TaskStatus) -> None:
        if self.status is not status:
            raise RuntimeError(f"Current task is not {status}; Status {self.status}")

    def _handle(self, method: str, params: list[Any]) -> Any:  # noqa: C901, PLR0911
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
                self._notifications.append("exp::ABORTED")
            case "exp.SetupTask":
                self._require(TaskStatus.IDLE)
                self.status = TaskStatus.SETUP
            case "exp.StartTask":
                self._require(TaskStatus.SETUP)
                self.status = TaskStatus.RUNNING
            case "exp.GetTaskStatus":
                return f"Status {self.status}, executed 0 / 2 shots in 0 ms\n"
            case "exp.GetTaskResults":
                self._require(TaskStatus.FINISHED)
                self.status = TaskStatus.IDLE
                return [DATA, {name: [] for name in DATA}, ""]
            case _:
                raise RuntimeError(f"Invalid request: {method}")
        return None


@pytest.fixture
def gateway() -> Iterator[FakeGateway]:
    fake = FakeGateway()
    yield fake
    fake.close()


def make_controller(gateway: FakeGateway, timeout: float = 2) -> RFSoCController:
    return RFSoCController(
        host="127.0.0.1", port=gateway.port, timeout=timeout, poll_interval=0.001
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
    # The nil-method notification did not break the connection, and was dropped
    assert controller.connected
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
    gateway.requests_until_finished = 100
    controller.connect()
    controller.send(SEQUENCE)
    assert gateway.status is TaskStatus.SETUP
    assert gateway.methods[-2:] == ["exp.AbortTask", "exp.SetupTask"]


def test_receive_aborts_timed_out_task(gateway: FakeGateway) -> None:
    gateway.requests_until_finished = 10_000
    controller = make_controller(gateway, timeout=0.05)
    controller.connect()
    controller.send(SEQUENCE)
    controller.run()
    with pytest.raises(TimeoutError):
        controller.receive()
    assert gateway.status is TaskStatus.IDLE
    assert gateway.methods[-1] == "exp.AbortTask"


def test_query_device_id_when_unreachable() -> None:
    with socket.create_server(("127.0.0.1", 0)) as server:
        port = server.getsockname()[1]
    controller = RFSoCController(host="127.0.0.1", port=port)
    controller.connect()
    assert controller.query_device_id() is None


def test_layout_is_empty_on_other_device() -> None:
    assert ChannelLayout.from_sequence(SEQUENCE, device_id="other") == ChannelLayout()


def test_layout_falls_back_to_full_decode() -> None:
    sparse = json.dumps(json.loads(SEQUENCE), indent=2)
    assert ChannelLayout.from_sequence(
        sparse, device_id=DEVICE_ID
    ) == ChannelLayout.from_sequence(SEQUENCE, device_id=DEVICE_ID)


def test_to_zedboard_readouts() -> None:
    layout = ChannelLayout.from_sequence(SEQUENCE, device_id=DEVICE_ID)
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
