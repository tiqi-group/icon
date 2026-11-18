# ruff: noqa: TC001 TC003
from __future__ import annotations

from datetime import datetime

import pydantic

from icon.server.data_access.experiment_data import DatabaseValueType
from icon.server.pre_processing.task import PreProcessingTask


class HardwareProcessingTask(pydantic.BaseModel):
    data_point_index: int
    pre_processing_task: PreProcessingTask
    priority: int
    scanned_params: dict[str, DatabaseValueType]
    global_parameter_timestamp: datetime
    hardware_instructions: list[tuple[str, str]]
    parameter_dict: dict[str, DatabaseValueType] = pydantic.Field(default_factory=dict)
    """Parameter values the hardware instructions were generated with."""
    src_dir: str | None
    created: datetime
