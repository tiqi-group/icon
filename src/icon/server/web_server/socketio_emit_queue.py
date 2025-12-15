from __future__ import annotations

import multiprocessing
from typing import Any, NotRequired, TypedDict


class EmitEvent(TypedDict):
    event: str
    data: Any
    room: NotRequired[str]


emit_queue: multiprocessing.Queue[EmitEvent] = multiprocessing.Queue()
