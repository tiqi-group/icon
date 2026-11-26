from __future__ import annotations

from multiprocessing.queues import Queue
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict


class EmitEvent(TypedDict):
    event: str
    data: Any
    room: NotRequired[str]


if TYPE_CHECKING:
    EmitQueue = Queue[EmitEvent]
else:
    # `Queue` is only subscriptable at runtime on Python 3.12+; the alias is
    # annotation-only, so the bare class suffices elsewhere.
    EmitQueue = Queue
"""Queue of socket.io events awaiting emission.

Created once in `start_server` and propagated to every consumer, so the queue is
always the one the web server consumes.
"""
