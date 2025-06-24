from __future__ import annotations

import logging
import multiprocessing
import re
from typing import TYPE_CHECKING

import pydase

from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataPoint,
    ExperimentDataRepository,
)
from icon.server.data_access.repositories.job_run_repository import (
    job_run_cancelled_or_failed,
)
from icon.server.hardware_processing.hardware_controller import HardwareController

if TYPE_CHECKING:
    import queue

    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.hardware_processing.task import HardwareProcessingTask
    from icon.server.shared_resource_manager import SharedResourceManager

logger = logging.getLogger(__name__)


def parse_parameter_id(param_id: str) -> tuple[str | None, str]:
    """Parses a parameter ID string into a device name and variable ID.

    If the input string is in the format "Device(device_name) variable_id",
    the device name and variable ID are returned as a tuple.

    Parameters:
        param_id: The parameter identifier string.

    Returns:
        A tuple (device_name, variable_id). If the input does not match the expected
        format, device_name is None and the entire param_id is returned as the
        variable_id.

    Examples:
        >>> parse_parameter_id("Device(my_device) my_param")
        ('my_device', 'my_param')

        >>> parse_parameter_id("bare_param")
        (None, 'bare_param')
    """

    match = re.match(r"^Device\(([^)]+)\) (.*)$", param_id)
    if match:
        return match[1], match[2]
    return None, param_id


class HardwareProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        hardware_processing_queue: queue.PriorityQueue[HardwareProcessingTask],
        manager: SharedResourceManager,
    ) -> None:
        super().__init__()
        self._queue = hardware_processing_queue
        self._manager = manager

    def _update_pydase_service_parameter(
        self, device_name: str, access_path: str, new_value: DatabaseValueType
    ) -> None:
        self._pydase_clients[device_name].update_value(
            access_path=access_path, new_value=new_value
        )
        # TODO: wait n seconds before trying to validate -> this value should be defined
        # per device -> store in devices table
        # TODO: repeat check n times if it fails -> also defined per device. If it still
        # fails, raise an exception and mark the job failed
        # TODO: add "rounding", i.e. bounds for rounding errors
        if (
            self._pydase_clients[device_name].get_value(access_path=access_path)
            != new_value
        ):
            logger.warning(
                "(hardware-worker) %r of device %r was probably not set correctly",
                access_path,
                device_name,
            )

    def _set_pydase_service_values(
        self, scanned_params: dict[str, DatabaseValueType]
    ) -> None:
        for param, value in scanned_params.items():
            device_name, access_path = parse_parameter_id(param_id=param)

            if device_name is None:
                continue

            client = self._pydase_clients.get(device_name, None)
            if client is None:
                client = pydase.Client(
                    url=DeviceRepository.get_device_by_name(name=device_name).url,
                    client_id="icon-hardware-worker",
                    auto_update_proxy=False,
                )
                self._pydase_clients[device_name] = client
            self._update_pydase_service_parameter(
                device_name=device_name, access_path=access_path, new_value=value
            )

    def run(self) -> None:
        self._pydase_clients = {
            device.name: pydase.Client(url=device.url, auto_update_proxy=False)
            for device in DeviceRepository.get_devices_by_status(
                status=DeviceStatus.ENABLED
            )
        }

        hardware_controller = HardwareController()

        while True:
            task = self._queue.get()

            if job_run_cancelled_or_failed(
                job_id=task.pre_processing_task.job.id,
                log_prefix="(hardware-worker)",
            ):
                continue

            self._set_pydase_service_values(scanned_params=task.scanned_params)

            result = hardware_controller.run(
                sequence=task.sequence_json,
                number_of_shots=task.pre_processing_task.job.number_of_shots,
            )

            experiment_data_point: ExperimentDataPoint = {
                "index": task.data_point_index,
                "scan_params": task.scanned_params,
                "result_channels": result["result_channels"],
                "shot_channels": result["shot_channels"],
                "vector_channels": result["vector_channels"],
                "timestamp": task.global_parameter_timestamp.isoformat(),
            }

            # TODO: move this to the post-processing worker
            ExperimentDataRepository.write_experiment_data_by_job_id(
                job_id=task.pre_processing_task.job.id,
                data_point=experiment_data_point,
            )

            task.processed_data_points.put(task.scanned_params)
