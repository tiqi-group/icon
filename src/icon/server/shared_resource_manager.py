from __future__ import annotations

import logging
import queue
from multiprocessing.managers import DictProxy, SyncManager
from typing import TYPE_CHECKING, Any

from icon.server.pre_processing import arbiter

if TYPE_CHECKING:
    from icon.server.data_access.experiment_data import DatabaseValueType
    from icon.server.pre_processing.task import PreProcessingTask

logger = logging.getLogger(__name__)


class SharedResourceManager(SyncManager):
    """Multiprocessing SyncManager that owns shared queues and dicts used across multiple server processes."""

    PriorityQueue: type[queue.PriorityQueue[Any]]
    Arbiter: type[arbiter.Arbiter]

    pre_processing_queue: queue.PriorityQueue[PreProcessingTask]
    task_arbiter: arbiter.Arbiter
    """The pre-processing workers' task queues, which the hardware worker pulls from."""
    parameters_dict: DictProxy[str, DatabaseValueType]

    def __init__(self) -> None:
        super().__init__()
        self.register("PriorityQueue", queue.PriorityQueue)
        self.register("Arbiter", arbiter.Arbiter)

    def start_srm(self) -> None:
        """Start the manager server process and initialize shared resources."""
        self.start(initializer=self.initializer)

        self.pre_processing_queue = self.PriorityQueue()
        self.task_arbiter = self.Arbiter()
        self.parameters_dict = self.dict()

    def initializer(self) -> None:
        logger.info("Shared resource manager started")


SRM = SharedResourceManager()
