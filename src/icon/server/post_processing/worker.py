import logging
import multiprocessing
import queue

from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataRepository,
)
from icon.server.data_access.repositories.job_run_repository import (
    job_run_cancelled_or_failed,
)
from icon.server.post_processing.task import PostProcessingTask

logger = logging.getLogger(__name__)


class PostProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        post_processing_queue: queue.PriorityQueue[PostProcessingTask],
    ) -> None:
        super().__init__()
        self._post_processing_queue = post_processing_queue

    def run(self) -> None:
        logger.info("Pre-processing worker started")

        while True:
            task = self._post_processing_queue.get()

            if job_run_cancelled_or_failed(
                job_id=task.pre_processing_task.job.id,
            ):
                continue

            ExperimentDataRepository.write_experiment_data_by_job_id(
                job_id=task.pre_processing_task.job.id,
                data_point=task.data_point,
            )
