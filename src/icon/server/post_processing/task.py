# ruff: noqa: TC001 TC003
from __future__ import annotations

from datetime import datetime

import pydantic

from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataPoint,
)
from icon.server.pre_processing.task import PreProcessingTask


class PostProcessingTask(pydantic.BaseModel):
    priority: int
    pre_processing_task: PreProcessingTask
    data_point: ExperimentDataPoint
    src_dir: str
    created: datetime

    def __lt__(self, other: PostProcessingTask) -> bool:
        return self.priority < other.priority
