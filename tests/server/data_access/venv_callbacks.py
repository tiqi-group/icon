"""Callbacks to run in an isolated environment.

The environment has only the standard library, so this module imports nothing else.
"""

import os
import sys
import time
import warnings

SLOW_CALLBACK_SECONDS = 10


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
    os._exit(3)


def slow_callback() -> None:
    time.sleep(SLOW_CALLBACK_SECONDS)


def large_instructions(size: int) -> dict[str, str]:
    """Return instructions of two devices, JSON strings of about ``size`` bytes each."""
    pulse = '{"channel": "rf0", "duration": 2.0}, '
    sequence = '{"pulses": [' + pulse * (size // len(pulse)) + "]}"
    return {"main": sequence, "sub": sequence}
