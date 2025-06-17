from __future__ import annotations

import queue
from multiprocessing.managers import DictProxy, SyncManager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.hardware_processing.task import HardwareProcessingTask
    from icon.server.post_processing.task import PostProcessingTask
    from icon.server.pre_processing.task import PreProcessingTask


class SharedResourceManager(SyncManager):
    PriorityQueue: type[queue.PriorityQueue[Any]]


manager = SharedResourceManager()
manager.register("PriorityQueue", queue.PriorityQueue)
manager.start()

# Create shared priority queues
pre_processing_queue: queue.PriorityQueue[PreProcessingTask] = manager.PriorityQueue()
hardware_queue: queue.PriorityQueue[HardwareProcessingTask] = manager.PriorityQueue()
post_processing_queue: queue.PriorityQueue[PostProcessingTask] = manager.PriorityQueue()
parameters_dict: DictProxy[str, DatabaseValueType] = manager.dict()
