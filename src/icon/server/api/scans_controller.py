from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pydase

if TYPE_CHECKING:
    import multiprocessing

logger = logging.getLogger(__name__)


class ScansController(pydase.DataService):
    """ScansController is responsible for triggering update events for jobs across
    multiple worker processes.

    Each worker process has its own update queue (multiprocessing.Queue), which this
    controller writes to when an update event is triggered.
    """

    def __init__(
        self,
        pre_processing_update_queues: list[multiprocessing.Queue[dict[str, Any]]],
    ) -> None:
        super().__init__()
        self._pre_processing_update_queues = pre_processing_update_queues

    async def trigger_update_job_params_by_id(self, *, job_id: int) -> None:
        """Triggers an 'update_parameters' event for the given job ID.

        Args:
            job_id: The ID of the job whose parameters should be updated.
        """

        for pre_processing_update_queue in self._pre_processing_update_queues:
            pre_processing_update_queue.put(
                {
                    "event": "update_parameters",
                    "job_id": job_id,
                }
            )
