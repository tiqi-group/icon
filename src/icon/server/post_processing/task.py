from __future__ import annotations

import pydantic


class PostProcessingTask(pydantic.BaseModel):
    priority: int

    def __lt__(self, other: PostProcessingTask) -> bool:
        return self.priority < other.priority
