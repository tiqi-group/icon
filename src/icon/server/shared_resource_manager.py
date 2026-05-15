from __future__ import annotations

import queue
from multiprocessing.managers import DictProxy, SyncManager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.hardware_processing.task import HardwareProcessingTask
    from icon.server.pre_processing.task import PreProcessingTask


class Counter:
    """An integer counter shared across processes via the manager.

    Used in place of a queue to track how many hardware tasks have been processed for
    a given job run, without retaining the full task objects in the manager process.
    """

    def __init__(self) -> None:
        self._value = 0

    def increment(self) -> None:
        self._value += 1

    def value(self) -> int:
        return self._value


class SharedResourceManager(SyncManager):
    PriorityQueue: type[queue.PriorityQueue[Any]]
    Counter: type[Counter]


manager = SharedResourceManager()
manager.register("PriorityQueue", queue.PriorityQueue)
manager.register("Counter", Counter, exposed=("increment", "value"))
manager.start()

# Create shared priority queues
pre_processing_queue: queue.PriorityQueue[PreProcessingTask] = manager.PriorityQueue()
hardware_processing_queue: queue.PriorityQueue[HardwareProcessingTask] = (
    manager.PriorityQueue()
)
parameters_dict: DictProxy[str, DatabaseValueType] = manager.dict()
