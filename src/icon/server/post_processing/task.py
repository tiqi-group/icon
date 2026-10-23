from collections.abc import Mapping
from datetime import datetime
from typing import Self

import pydantic
import pydase.units as u

from icon.server.data_access.experiment_data import ExperimentDataPoint
from icon.server.pre_processing.task import PreProcessingTask


class PostProcessingTask(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    priority: int
    pre_processing_task: PreProcessingTask
    data_point: ExperimentDataPoint
    src_dir: str | None
    created: datetime

    def __lt__(self, other: Self) -> bool:
        return self.priority < other.priority


# Note: Quantity needs to be in scope for pydantic
PostProcessingTask.model_rebuild(
    _types_namespace={"Quantity": u.Quantity, "Mapping": Mapping}
)
