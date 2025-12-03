# ruff: noqa: TC001 TC003
from __future__ import annotations

from datetime import datetime
from queue import PriorityQueue, Queue
from typing import TYPE_CHECKING, Any

import pydantic

from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.pre_processing.task import PreProcessingTask


class HardwareProcessingTask(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    data_point_index: int
    pre_processing_task: PreProcessingTask
    priority: int
    scanned_params: dict[str, DatabaseValueType]
    global_parameter_timestamp: datetime
    sequence_json: str
    src_dir: str
    created: datetime
    if TYPE_CHECKING:
        processed_data_points: Queue[HardwareProcessingTask]
        data_points_to_process: Queue[tuple[int, dict[str, DatabaseValueType]]]
        outdated_tasks: PriorityQueue[HardwareProcessingTask]
    else:
        # must be Any as the queues are AutoProxy instances, which I didn't figure out
        # how to type
        processed_data_points: Any
        data_points_to_process: Any
        outdated_tasks: Any

    def __lt__(self, other: HardwareProcessingTask) -> bool:
        return self.priority < other.priority or self.created < other.created
