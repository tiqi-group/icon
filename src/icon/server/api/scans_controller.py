from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pydase

from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.repositories.job_run_repository import JobRunRepository

if TYPE_CHECKING:
    import multiprocessing

    from icon.server.utils.types import UpdateQueue

logger = logging.getLogger(__name__)


class ScansController(pydase.DataService):
    """Controller for triggering update events for jobs across multiple worker processes.

    Each worker process has its own update queue (`[multiprocessing.Queue][]`), which
    this controller writes to when an update event is triggered.
    """

    def __init__(
        self,
        pre_processing_update_queues: list[multiprocessing.Queue[UpdateQueue]],
    ) -> None:
        super().__init__()
        self._pre_processing_update_queues = pre_processing_update_queues

    async def trigger_update_job_params(self, *, job_id: int | None = None) -> None:
        """Triggers an 'update_parameters' event for the given job ID.

        Args:
            job_id: The ID of the job whose parameters should be updated. If None, all
                jobs will update their parameters.
        """
        for pre_processing_update_queue in self._pre_processing_update_queues:
            pre_processing_update_queue.put(
                {
                    "event": "update_parameters",
                    "job_id": job_id,
                }
            )

    async def retake_data_points(self, *, job_id: int, no_data_points: int) -> None:
        """Triggers a 'retake_data_points' event for the given job ID.

        The job run must be paused. The last `no_data_points` data points are moved
        into invalid datasets in the HDF5 file and re-queued for re-acquisition.

        Args:
            job_id: ID of the job whose last data points should be retaken.
            no_data_points: Number of data points to be retaken.

        Raises:
            RuntimeError: If the job run is not paused.
        """
        job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)

        if job_run.status == JobRunStatus.PAUSED:
            for pre_processing_update_queue in self._pre_processing_update_queues:
                pre_processing_update_queue.put(
                    {
                        "event": "retake_data_points",
                        "job_id": job_id,
                        "no_data_points": no_data_points,
                    }
                )
        else:
            raise RuntimeError("Cannot retake data points when the job is not paused")
