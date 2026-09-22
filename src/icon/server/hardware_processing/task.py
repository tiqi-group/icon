# ruff: noqa: TC001 TC003
from __future__ import annotations

from datetime import datetime
from queue import PriorityQueue
from typing import TYPE_CHECKING, Any

import pydantic

from icon.server.data_access.experiment_data import DatabaseValueType
from icon.server.pre_processing.task import PreProcessingTask

if TYPE_CHECKING:
    from icon.server.shared_resource_manager import ScanProgress


class HardwareProcessingTask(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    data_point_index: int
    pre_processing_task: PreProcessingTask
    priority: int
    scanned_params: dict[str, DatabaseValueType]
    global_parameter_timestamp: datetime
    hardware_instructions: str
    src_dir: str | None
    created: datetime
    if TYPE_CHECKING:
        scan_progress: ScanProgress
        outdated_tasks: PriorityQueue[HardwareProcessingTask]
    else:
        # must be Any as these are AutoProxy instances, which I didn't figure out
        # how to type
        scan_progress: Any
        outdated_tasks: Any

    def __lt__(self, other: HardwareProcessingTask) -> bool:
        return (self.priority, self.created) < (other.priority, other.created)
