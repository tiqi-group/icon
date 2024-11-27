import asyncio
from typing import Any, ClassVar

import pydase
from pydase.task.decorator import task

from icon.config import get_config
from icon.server.api.models.experiment import Experiment


class ExperimentsController(pydase.DataService):
    _experiments: ClassVar[list[Experiment]] = []

    def get_experiments(self) -> list[Experiment]:
        return self._experiments
