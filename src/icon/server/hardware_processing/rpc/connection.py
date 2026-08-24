from __future__ import annotations

import contextlib
import logging
import select
import socket
import struct
import sys
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Final, override

import msgpack

from icon.server.hardware_processing.rpc.errors import (
    ConnectionBusyError,
    ProtocolError,
)

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)

HEADER_STRUCT: Final = struct.Struct("<I")
HEADER_SIZE: Final = HEADER_STRUCT.size

RECV_CHUNK_SIZE: Final = 256 * 1024
"""Socket reads are done in chunks of this size."""

DEFAULT_MAX_MESSAGE_SIZE: Final = 256 * 1024 * 1024
"""Msgpack maximum message size."""

_NOTHING: Final = object()

DEFAULT_KEEPALIVE_IDLE: Final = 10
DEFAULT_KEEPALIVE_INTERVAL: Final = 5
DEFAULT_KEEPALIVE_COUNT: Final = 3

MsgPackRecord = Any


def deadline_from(timeout: float | None) -> float | None:
    """Compute absolute deadline from timeout."""
    return None if timeout is None else time.monotonic() + timeout


def time_left(deadline: float | None) -> float | None:
    """Compute time left until deadline is reached.

    Returns:
        Remaining time in seconds. Always positive.

    Raises:
        TimeoutError: If ``deadline`` has already passed.
    """
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("timeout waiting for a response")
    return remaining


class Transaction:
    """Exclusive use of a connection for one exchange, under a single deadline.

    Handed out by :meth:`Connection.transaction`, which holds the connection's lock for as
    long as this object is in scope. Every read draws on the same budget, so a reply
    arriving behind a burst of notifications still cannot outlive the caller's timeout --
    and no call site has to do the arithmetic. That is the point of the object: the
    deadline is derived once, here, and no absolute time ever crosses the boundary.
    """

    def __init__(self, connection: Connection, deadline: float | None) -> None:
        self._connection = connection
        self._deadline = deadline

    def send(self, message: MsgPackRecord) -> None:
        """Encode and write one message."""
        self._connection.send(message)

    def receive(self) -> MsgPackRecord:
        """Wait for the next message, within what is left of the budget."""
        return self._connection._read_message(self._deadline)

    def try_receive(self) -> MsgPackRecord | None:
        """Return the next message if one is already available, else ``None``.

        Spends none of the budget, because it never waits.
        """
        return self._connection.try_receive()


class Connection:
    """Blocking connection with a raw msgpack stream.

    The connection is opened by :meth:`connect`. Every I/O operation must be wrapped in a
    :meth:`transaction` to be thread-safe.

    On any error, the connection is closed. The caller must explicitly re-open with :meth:`connect`.

    Args:
        hostname: Host to connect to.
        port: TCP port to connect to.
        timeout: Default bound in seconds, used for connecting and for any
            :meth:`receive` or :meth:`transaction` whose caller passes no timeout.
            ``None`` blocks indefinitely.
        lock_timeout: How long :meth:`transaction` waits for another thread's round trip
            to finish before giving up acquiring the lock.
        max_message_size: Messages larger than this will not be accepted and the connection closed.
        keepalive: Enable OS-level TCP keepalive.
        keepalive_idle: Seconds of inactivity before the first probe.
        keepalive_interval: Seconds between probes once they start.
        keepalive_count: Unanswered probes before the connection is declared dead.
        user_timeout: Seconds until sent data may go unacknowledged before the kernel
            declares the connection dead. Defaults to the full keepalive budget. Applied
            on Linux whether or not ``keepalive`` is set; ignored elsewhere.
    """

    def __init__(
        self,
        hostname: str,
        port: int,
        *,
        timeout: float | None = None,
        lock_timeout: float = 1.0,
        max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE,
        keepalive: bool = True,
        keepalive_idle: int = DEFAULT_KEEPALIVE_IDLE,
        keepalive_interval: int = DEFAULT_KEEPALIVE_INTERVAL,
        keepalive_count: int = DEFAULT_KEEPALIVE_COUNT,
        user_timeout: float | None = None,
    ) -> None:
        self._hostname = hostname
        self._port = port
        self._timeout = timeout
        self._lock_timeout = lock_timeout
        self._max_message_size = max_message_size
        self._keepalive = keepalive
        self._keepalive_idle = keepalive_idle
        self._keepalive_interval = keepalive_interval
        self._keepalive_count = keepalive_count
        self._user_timeout = (
            keepalive_idle + keepalive_interval * keepalive_count
            if user_timeout is None
            else user_timeout
        )

        self._lock = threading.Lock()
        self._packer = msgpack.Packer(use_bin_type=True)
        self._unpacker = self._new_unpacker()
        self._socket: socket.socket | None = None

    def connect(self) -> None:
        """Open the connection, replacing any socket this instance still holds.

        Idempotent, and the only way a socket is ever installed. Any previous socket is
        closed and the decoder is reset first, so no bytes left over from a dead stream
        can be spliced onto the new one and no file descriptor is orphaned.
        """
        with self._lock:
            self._close()
            self._reset_decoder()
            sock = socket.create_connection(
                (self._hostname, self._port), timeout=self._timeout
            )
            self._configure_socket(sock)
            self._socket = sock

    def __repr__(self) -> str:
        return f"msgpack(stream)://{self._hostname}:{self._port}"

    def _configure_socket(self, sock: socket.socket) -> None:
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            if self._keepalive:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                if sys.platform == "darwin":
                    keepalive_idle_opt = socket.TCP_KEEPALIVE
                else:
                    keepalive_idle_opt = socket.TCP_KEEPIDLE
                sock.setsockopt(
                    socket.IPPROTO_TCP, keepalive_idle_opt, self._keepalive_idle
                )
                sock.setsockopt(
                    socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self._keepalive_interval
                )
                sock.setsockopt(
                    socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self._keepalive_count
                )
            if sys.platform == "linux":
                sock.setsockopt(
                    socket.IPPROTO_TCP,
                    socket.TCP_USER_TIMEOUT,
                    round(self._user_timeout * 1000),
                )
        except (OSError, AttributeError):
            logger.warning(
                "Could not fully configure the socket options. Keepalive may not work.",
                exc_info=True,
            )

    def disconnect(self) -> None:
        """Close the connection."""
        with self._lock:
            self._close()

    def _close(self) -> None:
        """Close the socket. The caller must already hold the lock."""
        sock, self._socket = self._socket, None
        if sock is None:
            return
        with contextlib.suppress(OSError):
            sock.shutdown(socket.SHUT_RDWR)
        sock.close()

    @property
    def is_connected(self) -> bool:
        """Check if the socket is up.

        Reports False if FIN or RST was received. Idle or dead connections will report
        as connected until keepalive timeout is reached (if configured).
        """
        sock = self._socket
        if sock is None:
            return False
        try:
            readable, _, _ = select.select([sock], [], [], 0)
            if readable:
                data = sock.recv(1, socket.MSG_PEEK)
                if not data:
                    return False
        except OSError:
            return False
        return True

    def _new_unpacker(self) -> Any:
        return msgpack.Unpacker(raw=False, max_buffer_size=self._max_message_size)

    def _reset_decoder(self) -> None:
        """Drop every partially decoded byte. Called whenever a socket is installed."""
        self._unpacker = self._new_unpacker()

    def _sock(self) -> socket.socket:
        if self._socket is None:
            raise ConnectionError(f"not connected to {self!r}; call connect() first")
        return self._socket

    @contextmanager
    def locked(self) -> Generator[None]:
        """Hold the connection without starting an exchange.

        For operations that must not interleave with a round trip but send nothing
        themselves, such as reconnecting.

        Raises:
            ConnectionBusyError: if the connection lock could not be acquired within
                ``lock_timeout``.
        """
        if not self._lock.acquire(timeout=self._lock_timeout):
            raise ConnectionBusyError(
                f"connection still in use after {self._lock_timeout:g}s"
            )
        try:
            yield
        finally:
            self._lock.release()

    @contextmanager
    def transaction(self, timeout: float | None = None) -> Generator[Transaction]:
        """Context manager for owning the connection for one exchange.

        Blocks at most ``lock_timeout`` seconds on the connection lock.

        Args:
            timeout: Total time limit for the transaction to complete.
                ``None`` falls back to the connection's own ``timeout``.

        Yields:
            A :class:`Transaction` object for send/receive operations.

        A failed exchange closes the connection but never re-opens it. Once a read has
        timed out or the framing has desynced, the bytes still in flight belong to a
        request nobody is waiting for, so the stream cannot be reused -- but reconnecting
        here would do it silently, behind a caller that may have session state to
        re-establish (discovered ids, subscriptions) and no way to notice it must. So the
        socket is dropped, :attr:`is_connected` goes false, and reconnecting is the
        caller's decision.

        Raises:
            ConnectionBusyError: if the connection lock could not be acquired within
                ``lock_timeout``. Nothing was sent, so the connection stays healthy.
        """
        with self.locked():
            try:
                deadline = deadline_from(self._timeout if timeout is None else timeout)
                yield Transaction(self, deadline)
            except (OSError, ProtocolError):
                logger.debug("dropping %r after a failed exchange", self, exc_info=True)
                self._close()
                raise

    def send(self, message: MsgPackRecord) -> None:
        """Encode and write one message."""
        self._sock().sendall(self._packer.pack(message))

    def receive(self, timeout: float | None = None) -> MsgPackRecord:
        """Wait for the next message.

        Blocks until full message is received, potentially over multiple reads.

        Args:
            timeout: Seconds to wait for a whole message, potentially over multiple reads.
                ``None`` falls back to the connection's own ``timeout``.

        Returns:
            The unpacked opaque message.

        Raises:
            ProtocolError: If the bytes cannot belong to a valid msgpack stream.
            TimeoutError: If no complete message arrives in time.
            ConnectionError: If the peer closed the connection.
        """
        return self._read_message(
            deadline_from(self._timeout if timeout is None else timeout)
        )

    def try_receive(self) -> MsgPackRecord | None:
        """Non-blocking variant of :meth:`receive`. Suitable for polling.

        Consumes what the decoder already holds, plus whatever bytes are readable right
        now. A message that has only partly arrived stays buffered for the next call, so
        this never waits on the peer.
        """
        message = self._next_buffered()
        if message is not _NOTHING:
            return message
        chunk = self._recv_available(RECV_CHUNK_SIZE)
        if not chunk:
            return None
        self._feed(chunk)
        message = self._next_buffered()
        return None if message is _NOTHING else message

    def _read_message(self, deadline: float | None) -> MsgPackRecord:
        """Return the next message before absolute ``deadline`` is reached."""
        while True:
            message = self._next_buffered()
            if message is not _NOTHING:
                return message
            self._feed(self._recv(RECV_CHUNK_SIZE, deadline))

    def _feed(self, chunk: bytes) -> None:
        try:
            self._unpacker.feed(chunk)
        except (msgpack.UnpackException, ValueError) as exc:
            raise ProtocolError(f"malformed msgpack in stream: {exc}") from exc

    def _next_buffered(self) -> MsgPackRecord:
        """The next message the decoder already holds, or :data:`_NOTHING` if it has none."""
        try:
            return next(self._unpacker, _NOTHING)
        except (msgpack.UnpackException, ValueError) as exc:
            raise ProtocolError(f"malformed msgpack in stream: {exc}") from exc

    def _recv(self, size: int, deadline: float | None) -> bytes:
        """Read once, returning between 1 and ``size`` bytes."""
        sock = self._sock()
        sock.settimeout(time_left(deadline))
        chunk: bytes = sock.recv(size)
        if not chunk:
            # A zero-length read means EOF
            raise ConnectionResetError("The peer closed the connection")
        return chunk

    def _recv_available(self, size: int) -> bytes:
        """Read whatever is already there, returning ``b""`` when nothing is.

        Raises:
            ConnectionResetError: If the peer closed the connection.
        """
        sock = self._sock()
        readable, _, _ = select.select([sock], [], [], 0)
        if not readable:
            return b""
        sock.settimeout(0)
        try:
            chunk: bytes = sock.recv(size)
        except (BlockingIOError, InterruptedError):
            # Readability is advisory; another reader may have taken the bytes.
            return b""
        if not chunk:
            raise ConnectionResetError("The peer closed the connection")
        return chunk


class FramedConnection(Connection):
    """Connection with framed transport: single msgpack message following a 4-byte length header.

    Bytes are accumulated in one buffer that both the blocking and the polling read path
    draw on, so a frame that arrives in pieces is never half-consumed by a poll.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._buffer = bytearray()
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        return f"msgpack(framed)://{self._hostname}:{self._port}"

    @override
    def _new_unpacker(self) -> Any:
        """Framed messages are decoded whole, so no incremental decoder is needed."""
        return None

    @override
    def _reset_decoder(self) -> None:
        self._buffer.clear()

    @override
    def send(self, message: MsgPackRecord) -> None:
        """Override for the framed decode case. Prepend message with length header."""
        body: bytes = self._packer.pack(message)
        self._sock().sendall(HEADER_STRUCT.pack(len(body)) + body)

    @override
    def _read_message(self, deadline: float | None) -> MsgPackRecord:
        """Override for the framed decode case. Read header first, then read body with indicated length."""
        while True:
            message = self._next_buffered()
            if message is not _NOTHING:
                return message
            self._buffer += self._recv(RECV_CHUNK_SIZE, deadline)

    @override
    def try_receive(self) -> MsgPackRecord | None:
        while True:
            message = self._next_buffered()
            if message is not _NOTHING:
                return message
            chunk = self._recv_available(RECV_CHUNK_SIZE)
            if not chunk:
                return None
            self._buffer += chunk

    @override
    def _next_buffered(self) -> MsgPackRecord:
        """Take one complete frame out of the buffer, or :data:`_NOTHING` if none is whole yet."""
        if len(self._buffer) < HEADER_SIZE:
            return _NOTHING
        (length,) = HEADER_STRUCT.unpack_from(self._buffer)
        if not 0 < length <= self._max_message_size:
            raise ProtocolError(
                f"declared message size {length} is outside "
                f"(0, {self._max_message_size}]. Is the peer really speaking the framed "
                f"transport (framed=True)?"
            )
        end = HEADER_SIZE + length
        if len(self._buffer) < end:
            return _NOTHING
        body = memoryview(self._buffer)[HEADER_SIZE:end]
        try:
            message: MsgPackRecord = msgpack.unpackb(body, raw=False)
        except (msgpack.UnpackException, ValueError) as exc:
            raise ProtocolError(
                f"framed message of {length} bytes is not one msgpack object: {exc}"
            ) from exc
        finally:
            body.release()
            del self._buffer[:end]
        return message
