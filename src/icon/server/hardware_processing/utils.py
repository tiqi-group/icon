from __future__ import annotations

import ast
import re


def extract_hardware_error_message(exception: Exception) -> str:
    """Extract the error message from a hardware exception.

    ``tiqi_rpc`` wraps hardware errors as::

        RPCResponseError("Server reported msgid <N> error: [<code>, '<message>']")

    This strips the RPC wrapper and the error-code list, returning just the
    hardware message.  For any other exception the full string is returned.
    """
    msg = str(exception)
    # Strip "Server reported msgid <N> error: " prefix
    match = re.search(r"error: (.+)$", msg)
    if not match:
        return msg
    payload = match.group(1)
    # The RPC error payload is a repr of a Python object (typically a list
    # like [0, 'message']).  Try to parse it structurally so we don't depend
    # on regex for every possible error shape.
    try:
        parsed = ast.literal_eval(payload)
    except (ValueError, SyntaxError):
        return payload
    if isinstance(parsed, list | tuple):
        # Return the first string element (the human-readable message).
        for item in parsed:
            if isinstance(item, str):
                return item
    return payload
