import logging

import pydase

from icon.server.api.models.experiment_dict import (
    ExperimentDict,
)
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


class ExperimentsController(pydase.DataService):
    def __init__(self) -> None:
        super().__init__()
        self._experiments: ExperimentDict = {}

    def get_experiments(self) -> ExperimentDict:
        return self._experiments

    def _update_experiment_metadata(self, new_experiments: ExperimentDict) -> None:
        logger.debug("Updating experiment metadata...")

        self._experiments = new_experiments

        emit_queue.put(
            {
                "event": "experiments.update",
                "data": new_experiments,
            }
        )
