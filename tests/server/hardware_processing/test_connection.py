from __future__ import annotations

import socket
import sys

import msgpack
import pytest

from icon.server.hardware_processing.rpc.connection import Connection


@pytest.mark.skipif(sys.platform != "linux", reason="TCP_QUICKACK is Linux only")
@pytest.mark.parametrize("quickack", [True, False])
def test_receive_acknowledges_right_away(*, quickack: bool) -> None:
    with socket.create_server(("127.0.0.1", 0)) as server:
        connection = Connection(*server.getsockname(), timeout=1, quickack=quickack)
        connection.connect()
        peer, _ = server.accept()
        with peer:
            sock = connection._sock()
            # Delay the ACKs, as Linux does once requests and replies alternate
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 0)
            reply = msgpack.packb("reply")
            assert reply is not None
            peer.sendall(reply)

            assert connection.receive() == "reply"
            assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK) == quickack
        connection.disconnect()
