from dataclasses import asdict
from typing import Any

import pydase

from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataRepository,
)

__all__ = ["ExperimentDataController"]


class ExperimentDataController(pydase.DataService):
    """Controller for accessing stored experiment data.

    Provides API methods to fetch experiment data associated with jobs.
    """

    async def get_experiment_data_by_job_id(self, job_id: int) -> dict[str, Any]:
        """Return experiment data for a given job.

        Args:
            job_id: The unique identifier of the job.

        Returns:
            The experiment data linked to the job as a dict resulting
            from serializing a
             [ExperimentData][icon.server.data_access.repositories.experiment_data_repository.ExperimentData] instance.
        """

        return asdict(
            ExperimentDataRepository.get_experiment_data_by_job_id(job_id=job_id)
        )
