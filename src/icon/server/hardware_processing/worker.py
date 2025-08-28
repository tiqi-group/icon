from __future__ import annotations

import logging
import multiprocessing
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING

import pydase
import pytz
import socketio.exceptions

from icon.config.config import get_config
from icon.server.data_access.models.enums import DeviceStatus, JobRunStatus
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
    job_run_cancelled_or_failed,
)
from icon.server.hardware_processing.hardware_controller import HardwareController
from icon.server.post_processing.task import PostProcessingTask

if TYPE_CHECKING:
    import queue

    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.models.sqlite.device import Device
    from icon.server.data_access.repositories.experiment_data_repository import (
        ExperimentDataPoint,
    )
    from icon.server.hardware_processing.task import HardwareProcessingTask
    from icon.server.shared_resource_manager import SharedResourceManager

logger = logging.getLogger(__name__)
timezone = pytz.timezone(get_config().date.timezone)


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
        post_processing_queue: queue.PriorityQueue[PostProcessingTask],
        manager: SharedResourceManager,
    ) -> None:
        super().__init__()
        self._queue = hardware_processing_queue
        self._post_processing_queue = post_processing_queue
        self._manager = manager
        self._pydase_clients: dict[str, pydase.Client] = {}

        self._hardware_controller = HardwareController()

    def _update_pydase_service_parameter(
        self, device: Device, access_path: str, new_value: DatabaseValueType
    ) -> None:
        client = self._pydase_clients[device.name]
        try:
            client.update_value(access_path=access_path, new_value=new_value)
        except socketio.exceptions.BadNamespaceError:
            raise RuntimeError(
                f"Failed to connect to device {device.name!r} as {device.url!r}."
            )

        for attempt in range(1, device.retry_attempts + 1):
            value_on_device = client.get_value(access_path=access_path)
            # TODO: check for rounding errors
            if value_on_device == new_value:
                return
            logger.error(
                "Attempt %d: %r of device %r was not set correctly (got %r)",
                attempt,
                access_path,
                device.name,
                value_on_device,
            )
            if attempt < device.retry_attempts:
                time.sleep(device.retry_delay_seconds)

        raise RuntimeError(
            f"Failed to set {access_path!r} of device {device.name!r} after "
            f"{device.retry_attempts} attempts."
        )

    def _add_device(self, device: Device) -> None:
        self._pydase_clients[device.name] = pydase.Client(
            url=device.url,
            client_id="icon-hardware-worker",
            auto_update_proxy=False,
        )

    def _set_pydase_service_values(
        self, scanned_params: dict[str, DatabaseValueType]
    ) -> None:
        for param, value in scanned_params.items():
            device_name, access_path = parse_parameter_id(param_id=param)

            if device_name is None:
                continue

            device = DeviceRepository.get_device_by_name(name=device_name)

            if not device.status == DeviceStatus.ENABLED:
                raise RuntimeError(
                    f"Device {device.name!r} is disabled and cannot be scanned."
                )

            if device_name not in self._pydase_clients:
                self._add_device(device=device)

            self._update_pydase_service_parameter(
                device=device,
                access_path=access_path,
                new_value=value,
            )

    def run(self) -> None:
        self._pydase_clients = {
            device.name: pydase.Client(
                url=device.url, block_until_connected=False, auto_update_proxy=False
            )
            for device in DeviceRepository.get_devices_by_status(
                status=DeviceStatus.ENABLED
            )
        }

        while True:
            task = self._queue.get()

            if job_run_cancelled_or_failed(
                job_id=task.pre_processing_task.job.id,
            ):
                continue

            try:
                self._set_pydase_service_values(scanned_params=task.scanned_params)

                timestamp = datetime.now(timezone)
                result = self._hardware_controller.run(
                    sequence=task.sequence_json,
                    number_of_shots=task.pre_processing_task.job.number_of_shots,
                )

                experiment_data_point: ExperimentDataPoint = {
                    "index": task.data_point_index,
                    "scan_params": task.scanned_params,
                    "result_channels": result["result_channels"],
                    "shot_channels": result["shot_channels"],
                    "vector_channels": result["vector_channels"],
                    "timestamp": timestamp.isoformat(),
                    "sequence_json": task.sequence_json,
                }

                post_processing_task = PostProcessingTask(
                    priority=task.priority,
                    pre_processing_task=task.pre_processing_task,
                    data_point=experiment_data_point,
                    src_dir=task.src_dir,
                    created=task.created,
                )

                self._post_processing_queue.put(post_processing_task)
            except Exception as e:
                logger.exception(e)
                JobRunRepository.update_run_by_id(
                    run_id=task.pre_processing_task.job_run.id,
                    status=JobRunStatus.FAILED,
                    log=str(e),
                )
            finally:
                task.processed_data_points.put(task)
