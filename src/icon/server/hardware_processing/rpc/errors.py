"""Exception hierarchy for the RPC client."""

from __future__ import annotations

from typing import Any


class RPCError(Exception):
    """Base class for every error this package defines."""


class RPCResponseError(RPCError):
    """The server answered a request with a non-``nil`` ``error`` field.

    The payload has the form ``[code, "message"]``.

    :func:`icon.server.hardware_processing.utils.extract_hardware_error_message` parses the
    ``error: `` prefix to pull the hardware message out for
    ``hardware_processing/worker.py``, so it must not change without updating that helper.
    """

    def __init__(self, msgid: int, error: Any) -> None:
        super().__init__(f"Server reported msgid {msgid:d} error: {error}")
        self.msgid = msgid
        self.error = error


class ConnectionBusyError(RPCError, TimeoutError):
    """The thread lock could not be acquired within ``lock_timeout``."""


class ProtocolError(RPCError):
    """A server message could not be decoded.

    This error is fatal to the connection as it otherwise lead to desynchronization between
    client and server. Recover by opening the connection again.
    """


class RFSoCError(RPCError):
    """The device is configured differently than the client expects.

    When reading and evaluating server state like page, parameter or remote action
    this error indicates unexpected results mich may indicate misconfiguration.
    """
