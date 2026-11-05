"""Callbacks to run in an isolated environment.

The environment has only the standard library, so this module imports nothing else.
"""

import atexit
import ctypes
import os
import signal
import sys
import time
import warnings

SLOW_CALLBACK_SECONDS = 10

_kept: list[bytes] = []
"""Memory `keep_memory` keeps until the process exits."""


def callback_with_warning() -> dict[str, int]:
    warnings.warn("Some Warning", category=RuntimeWarning, stacklevel=42)
    return {"status": 0}


def process_id() -> int:
    return os.getpid()


def callback_with_output() -> str:
    print("to stdout")  # noqa: T201
    print("to stderr", file=sys.stderr)  # noqa: T201
    # Like an extension module, bypassing sys.stderr
    os.write(2, b"from C\n")
    warnings.warn("Some Warning", category=RuntimeWarning, stacklevel=1)
    return "done"


def failing_callback() -> None:
    raise ValueError("bad sequence")


def exiting_callback() -> None:
    print("to stdout before exiting", flush=True)  # noqa: T201
    print("giving up", file=sys.stderr, flush=True)  # noqa: T201
    os._exit(3)


def sys_exiting_callback() -> None:
    sys.exit("library gave up")


def killed_callback() -> None:
    """Die like a process the kernel kills for running out of memory."""
    os.kill(os.getpid(), signal.SIGKILL)


def segfaulting_callback() -> None:
    ctypes.string_at(0)


def callback_writing_a_malformed_response(size: int, body: str) -> str:
    """Write a malformed response, of ``size`` and ``body``, ahead of the real one."""
    # The runtime's response pipe, see `_RuntimeProcess`
    os.write(int(sys.argv[2]), size.to_bytes(8, "big") + body.encode())
    return "done"


def callback_writing_on_exit() -> None:
    atexit.register(print, "bye", file=sys.stderr)


def slow_callback() -> None:
    time.sleep(SLOW_CALLBACK_SECONDS)


def announced_slow_callback(started: str) -> None:
    """Like `slow_callback`, writing the process ID to the file ``started`` first."""
    _announce(started)
    time.sleep(SLOW_CALLBACK_SECONDS)


def keep_memory(size: int) -> None:
    """Take ``size`` bytes of memory until the process exits, like a leak."""
    # Written to, so that they are resident
    _kept.append(b"\x01" * size)


def announced_memory_leak(started: str, size: int) -> None:
    """Like `keep_memory` after a second, writing the process ID to ``started`` first."""
    _announce(started)
    time.sleep(1)
    keep_memory(size)


def _announce(started: str) -> None:
    """Write the process ID to the file ``started``."""
    with open(started + ".tmp", "w") as file:
        file.write(str(os.getpid()))
    # Complete once it exists
    os.rename(started + ".tmp", started)


def large_instructions(size: int) -> dict[str, str]:
    """Return instructions of two devices, JSON strings of about ``size`` bytes each."""
    pulse = '{"channel": "rf0", "duration": 2.0}, '
    sequence = '{"pulses": [' + pulse * (size // len(pulse)) + "]}"
    return {"main": sequence, "sub": sequence}
