import pydase

from icon.server.api.experiment_library_controller import ExperimentLibraryController
from icon.server.api.scheduler_controller import SchedulerController


class APIService(pydase.DataService):
    scheduler = SchedulerController()
    experiment_library = ExperimentLibraryController()
    parameters = None
