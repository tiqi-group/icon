import logging

import pydase

from icon.server.api.models.experiment_dict import (
    ExperimentDict,
)
from icon.server.api.parameters_controller import get_added_removed_and_updated_keys
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


class ExperimentsController(pydase.DataService):
    """Controller for experiment metadata.

    Stores the current set of experiments and exposes them to the API.
    Updates are compared against the existing metadata and, if changes
    are detected, an update event is pushed to the Socket.IO emit queue.
    """

    def __init__(self) -> None:
        super().__init__()
        self._experiments: ExperimentDict = {}

    def get_experiments(self) -> ExperimentDict:
        """Return the current experiment metadata.

        Returns:
            Mapping of experiment IDs to their metadata.
        """

        return self._experiments

    def _update_experiment_metadata(self, new_experiments: ExperimentDict) -> None:
        """Replace experiment metadata and emit an update event if changed.

        Compares the current and new metadata to detect added, removed, or updated
        experiments. If any changes are found, the new metadata is stored and an
        `"experiments.update"` event is placed in the Socket.IO emit queue.

        Args:
            new_experiments: Latest experiment metadata.
        """

        logger.debug("Updating experiment metadata...")

        added_exps, removes_exps, updated_exps = get_added_removed_and_updated_keys(
            self._experiments, new_experiments
        )
        self._experiments = new_experiments

        if added_exps or removes_exps or updated_exps:
            emit_queue.put(
                {
                    "event": "experiments.update",
                    "data": new_experiments,
                }
            )
