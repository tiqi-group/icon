import pydase

from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentData,
    ExperimentDataRepository,
)


class ExperimentDataController(pydase.DataService):
    async def get_experiment_data_by_job_id(self, job_id: int) -> ExperimentData:
        return ExperimentDataRepository.get_experiment_data_by_job_id(job_id=job_id)
