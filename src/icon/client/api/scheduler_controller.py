import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from icon.server.api.models.experiment import Experiment

if TYPE_CHECKING:
    from icon.client.client import Client

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class SchedulerController:
    def __init__(self, client: "Client") -> None:
        self._client = client

    def submit_job(
        self,
        *,
        experiment: Experiment,
        priority: int,
        local_parameters_timestamp: datetime,
        # scan_info: ScanInfo,
    ) -> Any:
        return self._client.trigger_method(
            "scheduler.submit_job",
            kwargs={
                "experiment": experiment,
                "priority": priority,
                "local_parameters_timestamp": local_parameters_timestamp,
                # "scan_info": scan_info,
            },
        )
