from __future__ import annotations

import logging
import queue
import threading
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


class ScanProgress:
    """Counts the finished data points of a scan.

    This class is instantiated once per PreProcessingWorker and tracks the progress
    of the currently active job run. The HardwareProcessingWorker increments
    with the :meth:`complete` call. The PreProcessingWorker periodically checks
    the :meth:`completed` count against the expected value.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._run_id: int | None = None
        self._completed = 0

    def start(self, run_id: int) -> None:
        """Begin counting for ``run_id``, discarding any earlier run's progress."""
        with self._lock:
            self._run_id = run_id
            self._completed = 0

    def complete(self, run_id: int) -> None:
        """Record one finished data point, ignoring runs that are no longer current."""
        with self._lock:
            if run_id == self._run_id:
                self._completed += 1

    def completed(self, run_id: int) -> int:
        """Data points finished for ``run_id``, or 0 if it is not the current run."""
        with self._lock:
            return self._completed if run_id == self._run_id else 0


class SharedResourceManager(SyncManager):
    """Multiprocessing SyncManager that owns shared queues and dicts used across multiple server processes."""

    PriorityQueue: type[queue.PriorityQueue[Any]]
    ScanProgress: type[ScanProgress]

    pre_processing_queue: queue.PriorityQueue[PreProcessingTask]
    hardware_processing_queue: queue.PriorityQueue[HardwareProcessingTask]
    parameters_dict: DictProxy[str, DatabaseValueType]

    def __init__(self) -> None:
        super().__init__()
        self.register("PriorityQueue", queue.PriorityQueue)
        self.register("ScanProgress", ScanProgress)

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
