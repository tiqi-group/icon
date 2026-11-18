# ruff: noqa: TC001 TC003
from __future__ import annotations

from datetime import datetime

import pydantic

from icon.server.data_access.experiment_data import (
    DatabaseValueType,
    ExperimentDataPoint,
)
from icon.server.pre_processing.task import PreProcessingTask


class PostProcessingTask(pydantic.BaseModel):
    priority: int
    pre_processing_task: PreProcessingTask
    data_point: ExperimentDataPoint
    parameter_dict: dict[str, DatabaseValueType] = pydantic.Field(default_factory=dict)
    """Parameter values the data point's hardware instructions were generated with."""
    src_dir: str | None
    created: datetime

    def __lt__(self, other: PostProcessingTask) -> bool:
        return self.priority < other.priority
