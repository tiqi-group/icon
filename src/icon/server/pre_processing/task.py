from __future__ import annotations

from datetime import datetime  # noqa: TCH003 Need this for pydantic's type inference

import pydantic


class PreProcessingTask(pydantic.BaseModel):
    job_id: int
    job_run_id: int
    experiment_id: str
    git_commit_hash: str | None = None
    priority: int = pydantic.Field(ge=0, le=20)
    local_parameters_timestamp: datetime
    # scan_parameters: list[int]
    auto_calibration: bool
    debug_mode: bool = False
    repetitions: int = 1

    def __lt__(self, other: PreProcessingTask) -> bool:
        return self.priority < other.priority
