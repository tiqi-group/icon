from __future__ import annotations

import pydantic


class PreProcessingTask(pydantic.BaseModel):
    name: str
    priority: int
    timestamp: float
    no_data_points: int
    git_hash: str | None = None
    debug_mode: bool = False

    def __lt__(self, other: PreProcessingTask) -> bool:
        return self.priority < other.priority
