import logging
import queue
from multiprocessing.managers import DictProxy, SyncManager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from icon.server.data_access.experiment_data import DatabaseValueType
    from icon.server.hardware_processing.task import HardwareProcessingTask
    from icon.server.pre_processing.task import PreProcessingTask

logger = logging.getLogger(__name__)

HARDWARE_PROCESSING_QUEUE_MAX_SIZE = 10
"""Maximum number of tasks allowed in the hardware processing queue before it blocks.
This avoids excessive queue growth during long running real-time scans."""


class SharedResourceManager(SyncManager):
    """Multiprocessing SyncManager that owns shared queues and dicts used across multiple server processes."""

    PriorityQueue: type[queue.PriorityQueue[Any]]

    pre_processing_queue: "queue.PriorityQueue[PreProcessingTask]"
    hardware_processing_queue: "queue.PriorityQueue[HardwareProcessingTask]"
    parameters_dict: "DictProxy[str, DatabaseValueType]"

    def __init__(self) -> None:
        super().__init__()
        self.register("PriorityQueue", queue.PriorityQueue)

    def start_srm(self) -> None:
        """Start the manager server process and initialize shared resources."""
        self.start(initializer=self.initializer)

        self.pre_processing_queue = self.PriorityQueue()
        self.hardware_processing_queue = self.PriorityQueue(
            maxsize=HARDWARE_PROCESSING_QUEUE_MAX_SIZE
        )
        self.parameters_dict = self.dict()

    def initializer(self) -> None:
        logger.info("Shared resource manager started")


SRM = SharedResourceManager()
