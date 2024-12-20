from datetime import datetime

import pydantic

from icon.server.pre_processing.task import PreProcessingTask


class HardwareProcessingTask(pydantic.BaseModel):
    pre_processing_task: PreProcessingTask
    priority: int
    data_point: dict[str, float]
    global_parameter_timestamp: datetime
    sequence_json: str
    src_dir: str

    def __lt__(self, other: "HardwareProcessingTask") -> bool:
        return self.priority < other.priority
