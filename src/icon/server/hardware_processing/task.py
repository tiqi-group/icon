from datetime import datetime
from typing import TYPE_CHECKING, Any

import pydantic

from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.pre_processing.task import PreProcessingTask

if TYPE_CHECKING:
    from queue import Queue


class HardwareProcessingTask(pydantic.BaseModel):
    data_point_index: int
    pre_processing_task: PreProcessingTask
    priority: int
    scanned_params: dict[str, DatabaseValueType]
    global_parameter_timestamp: datetime
    sequence_json: str
    src_dir: str
    processed_data_points: "Queue[Any]"
    data_points_to_process: "Queue[Any]"

    def __lt__(self, other: "HardwareProcessingTask") -> bool:
        return self.priority < other.priority
