import pydase

from icon.server.api.configuration_controller import ConfigurationController
from icon.server.api.experiments_controller import ExperimentsController
from icon.server.api.parameters_controller import ParametersController
from icon.server.api.scheduler_controller import SchedulerController


class APIService(pydase.DataService):
    scheduler = SchedulerController()
    experiments = ExperimentsController()
    parameters = ParametersController()
    config = ConfigurationController()
