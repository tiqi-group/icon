from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic

if TYPE_CHECKING:
    from datetime import datetime


class PreProcessingTask(pydantic.BaseModel):
    name: str
    experiment_file_path: str
    experiment_name: str
    git_commit_hash: str | None = None
    priority: int = pydantic.Field(ge=0, le=20)
    local_parameters_timestamp: datetime
    # scan_parameters: list[int]
    auto_calibration: bool
    debug_mode: bool = False

    def __lt__(self, other: PreProcessingTask) -> bool:
        return self.priority < other.priority
