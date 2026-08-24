"""Blocking client for lock-step msgpack-rpc. Only one .call() can be in flight.

REQUEST      := [0, msgid_u32, method: str, params: array]
RESPONSE     := [1, msgid_u32, error, result]
NOTIFICATION := [2, method: str, params]
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Final

from icon.server.hardware_processing.rpc.connection import (
    Connection,
    FramedConnection,
    MsgPackRecord,
)
from icon.server.hardware_processing.rpc.errors import (
    ConnectionBusyError,
    ProtocolError,
    RPCResponseError,
)

logger = logging.getLogger(__name__)


class MessageType(IntEnum):
    """First element of every msgpack-rpc message array."""

    REQUEST = 0
    RESPONSE = 1
    NOTIFICATION = 2


@dataclass(frozen=True, slots=True)
class RPCNotification:
    """A message the server pushed of its own accord, answering no request."""

    method: str
    params: Any


@dataclass(frozen=True, slots=True)
class RPCResponse:
    """A reply to one request, tied to it by :attr:`msgid` rather than by arrival order."""

    msgid: int
    error: Any
    result: Any

DEFAULT_LOCK_ACQUSITION_TIME: Final = 1.0
"""Default time for a RPC round-trip lock to become available."""

DEFAULT_NOTIFICATION_LIMIT: Final = 100
"""Default consumption batch size when calling :meth:`MsgPackRPCClient.consume_notifications`"""

DEFAULT_NOTIFICATION_BUFFER: Final = 1000
"""Notifications retained while nobody polls. Past this the oldest are dropped, which is
    reported once per poll rather than once per message."""

def _Brief(x: Any) -> Any:
    return x


class MsgPackRPCClient:
    """Blocking msgpack-rpc client, with one request in flight at a time.

    Call :meth:`connect` to open the connection.

    For example::

        client = MsgPackRPCClient("localhost", 1234)
        client.connect()
        print(client.call("hello"))

    Args:
        hostname: Host to connect to.
        port: TCP port to connect to.
        timeout: Default timeout for a call, in seconds, counted from when the request is
            sent. ``None`` waits indefinitely.
        framed: Whether to use framed transport, where every message is preceeded with a 4-byte length header.
        lock_timeout: How long a call waits for another thread's round trip to finish.
        notification_buffer: How many pushed notifications to retain in the buffer.
            Oldest are dropped first.
    """

    def __init__(
        self,
        hostname: str,
        port: int,
        timeout: float | None = None,
        *,
        framed: bool = True,
        lock_timeout: float = DEFAULT_LOCK_ACQUSITION_TIME,
        notification_buffer: int = DEFAULT_NOTIFICATION_BUFFER,
    ) -> None:
        self._timeout = timeout
        self._msgid = 0
        self._notification_buffer = notification_buffer
        self._notifications: deque[tuple[float, Any]] = deque(
            maxlen=notification_buffer
        )
        self._dropped = 0

        self._connection = (FramedConnection if framed else Connection)(
            hostname, port, timeout=timeout, lock_timeout=lock_timeout
        )

    def __repr__(self) -> str:
        return f"MsgPackRPCClient[conn={self._connection}, timeout={self._timeout}, msgid={self._msgid}, pending_notify={len(self._notifications)}]"

    def connect(self) -> None:
        self._connection.connect()

    def disconnect(self) -> None:
        self._connection.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._connection.is_connected

    @property
    def _next_msgid(self) -> int:
        msgid = self._msgid
        self._msgid = (self._msgid + 1) & 0xFFFF_FFFF
        return msgid

    def call(self, method_name: str, *args: Any, timeout: float | None = None) -> Any:
        """Invoke a blocking remote function call and return its result.

        Args:
            method_name: The name of the RPC method to call.
            *args: Positional arguments passed to the RPC method.
            timeout: Maximum time to wait for a response, in seconds. Uses the
                client's default timeout when omitted.

        Returns:
            The ``result`` field of the server's reply, unpacked.

        Raises:
            RPCResponseError: If the server answers with an error.
            ProtocolError: If the server sends something unreadable.
            TimeoutError: If no response arrives within ``timeout``.
            ConnectionBusyError: If another thread holds the connection. Nothing was
                sent, so retrying is safe.
            ConnectionError: If the connection is not open, or the peer closed it.
        """
        logger.debug("call: %s%s", method_name, _Brief(args))
        _timeout = self._timeout if timeout is None else timeout

        with self._connection.transaction(_timeout) as transaction:
            msgid = self._next_msgid
            transaction.send((MessageType.REQUEST, msgid, method_name, args))

            while True:
                received = self._route(transaction.receive())
                if not isinstance(received, RPCResponse):
                    continue  # a notification, already buffered
                if received.msgid != msgid:
                    logger.warning(
                        "discarding response for msgid %d while awaiting %d",
                        received.msgid,
                        msgid,
                    )
                    continue
                if received.error is not None:
                    raise RPCResponseError(msgid, received.error)
                return received.result

    def _route(self, message: MsgPackRecord) -> RPCNotification | RPCResponse:
        """Decompose the RPC message type out of the generic MsgPackRecord.

        Raises:
            ProtocolError: The record is an unknown message type
        """
        match message:
            case [MessageType.NOTIFICATION, str(method), params]:
                notification = RPCNotification(method, params)
                logger.debug(
                    "> NOTIFICATION %s%s",
                    notification.method,
                    _Brief(notification.params),
                )
                if len(self._notifications) == self._notification_buffer:
                    self._dropped += 1
                self._notifications.append((time.time(), params))
                return notification
            case [MessageType.RESPONSE, int(msgid), error, result]:
                logger.debug(
                    "> RESPONSE (%d) %s%s", msgid, _Brief(error), _Brief(result)
                )
                return RPCResponse(msgid, error, result)
            case _:
                raise ProtocolError(f"not a msgpack-rpc message: {message!r}")

    def notify(self, method_name: str, *args: Any) -> None:
        """Send a one-way notification, for which the server sends no reply."""
        logger.debug("notify: %s%s", method_name, _Brief(args))
        with self._connection.transaction() as transaction:
            transaction.send((MessageType.NOTIFICATION, method_name, args))

    def consume_notifications(
        self, limit: int = DEFAULT_NOTIFICATION_LIMIT
    ) -> list[tuple[float, Any]]:
        """Return up to ``limit`` received notifications.

        Reads the socket for more only if fewer than ``limit`` are already buffered, and
        only what has already arrived. A connection busy with a call is not an error here:
        that call is reading the same socket and buffers every notification it passes, so
        the poll gives up its turn and returns what it has.
        """
        limit = min(limit, self._notification_buffer)
        if len(self._notifications) < limit:
            # Notification queue holds less than requested. Check if we can drain the
            # connection for more.
            try:
                with self._connection.transaction() as transaction:
                    while (
                        len(self._notifications) < limit
                        and (message := transaction.try_receive()) is not None
                    ):
                        _ = self._route(message)
            except ConnectionBusyError:
                logger.debug("connection busy; returning what is already buffered")

        if self._dropped:
            logger.warning(
                "dropped %d notification(s): the buffer holds %d and was not polled in time",
                self._dropped,
                self._notification_buffer,
            )
            self._dropped = 0
        return [
            self._notifications.popleft()
            for _ in range(min(limit, len(self._notifications)))
        ]
