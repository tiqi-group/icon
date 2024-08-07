import pydase

from icon.server.api.models.experiment import Experiment


class ExperimentLibraryController(pydase.DataService):
    def get_experiments(self) -> list[Experiment]: ...
