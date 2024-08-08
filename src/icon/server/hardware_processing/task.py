from __future__ import annotations

import pydantic


class HardwareProcessingTask(pydantic.BaseModel):
    priority: int

    def __lt__(self, other: HardwareProcessingTask) -> bool:
        return self.priority < other.priority
