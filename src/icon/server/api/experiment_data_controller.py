import asyncio
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

    async def get_experiment_data_by_job_id(
        self, job_id: int, max_data_points: int = 10_000
    ) -> dict[str, Any]:
        """Return experiment data for a given job.

        Args:
            job_id: The unique identifier of the job.
            max_data_points: Maximum number of data points to load from the
                HDF5 file.  When the file contains more, only the last
                *max_data_points* are returned.

        Returns:
            The experiment data linked to the job as a dict resulting
            from serializing an
            [ExperimentData][icon.server.data_access.repositories.experiment_data_repository.ExperimentData]
            instance.
        """

        result = await asyncio.to_thread(
            ExperimentDataRepository.get_experiment_data_by_job_id,
            job_id=job_id,
            max_data_points=max_data_points,
        )
        return asdict(result)
