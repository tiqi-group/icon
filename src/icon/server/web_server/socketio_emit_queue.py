from __future__ import annotations

import multiprocessing
from typing import Any

import sys
if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired

if sys.version_info < (3, 12):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict


class EmitEvent(TypedDict):
    event: str
    data: Any
    room: NotRequired[str]


emit_queue: multiprocessing.Queue[EmitEvent] = multiprocessing.Queue()
