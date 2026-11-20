from __future__ import annotations

import logging
import multiprocessing
from typing import TYPE_CHECKING

from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataRepository,
)
from icon.server.data_access.repositories.job_run_repository import (
    try_update_run_by_id,
)
from icon.server.utils.handle_keyboard_interrupt import handle_keyboard_interrupt

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from icon.config.config import Config
    from icon.server.data_access.db_context.sqlite.engine import CachedEngine
    from icon.server.post_processing.task import PostProcessingTask

logger = logging.getLogger(__name__)


class PostProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        config: Config,
        post_processing_queue: multiprocessing.Queue[PostProcessingTask],
        engine_cache: CachedEngine,
    ) -> None:
        super().__init__()
        self._icon_config = config
        self._post_processing_queue = post_processing_queue
        self._engine_cache = engine_cache

    def _engine(self) -> Engine:
        return self._engine_cache.get_cached(
            self._icon_config.get().databases.sqlite.file
        )

    @handle_keyboard_interrupt(logger)
    def run(self) -> None:
        logger.info("Post-processing worker started")

        while True:
            # Tasks of failed or cancelled jobs are still processed: they hold data
            # points measured before the job stopped, or the hardware instructions
            # of the data point that failed on the device.
            task = self._post_processing_queue.get()

            try:
                ExperimentDataRepository.from_config(
                    self._icon_config, engine=self._engine()
                ).write_experiment_data_by_job_id(
                    job_id=task.pre_processing_task.job.id,
                    data_point=task.data_point,
                )
            except Exception as e:
                logger.exception(
                    "Post-processing of job with id '%s' failed",
                    task.pre_processing_task.job.id,
                )
                # Keep the status and log of runs that already failed or were
                # cancelled, e.g. the hardware error message.
                try_update_run_by_id(
                    engine=self._engine(),
                    run_id=task.pre_processing_task.job_run.id,
                    status=JobRunStatus.FAILED,
                    log=f"Post-processing error: {e}",
                    only_if_status=(
                        JobRunStatus.PROCESSING,
                        JobRunStatus.PAUSED,
                        JobRunStatus.DONE,
                    ),
                )
