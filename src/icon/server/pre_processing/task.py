import pydantic

from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter


class PreProcessingTask(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    job: Job
    job_run: JobRun
    git_commit_hash: str | None = None
    priority: int = pydantic.Field(ge=0, le=20)
    local_parameters_timestamp: str
    scan_parameters: list[ScanParameter]
    auto_calibration: bool
    debug_mode: bool = False
    repetitions: int = 1

    def __lt__(self, other: "PreProcessingTask") -> bool:
        return self.priority < other.priority
