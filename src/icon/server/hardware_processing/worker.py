from __future__ import annotations

import logging
import multiprocessing
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pydase
import pytz
import socketio.exceptions
from pydase.utils.serialization.serializer import dump

from icon.config.config import get_config
from icon.server.data_access.experiment_data import (
    ExperimentDataPoint,
    ExperimentDeviceDataPoint,
    HardwareProcessingError,
    Readouts,
)
from icon.server.data_access.models.enums import DeviceStatus, JobRunStatus
from icon.server.data_access.models.sqlite.scan_parameter import (
    contains_realtime_parameter,
)
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
    try_update_run_by_id,
)
from icon.server.hardware_processing.hardware_controller import HardwareController
from icon.server.hardware_processing.rpc.errors import RPCResponseError
from icon.server.hardware_processing.utils import extract_hardware_error_message
from icon.server.post_processing.task import PostProcessingTask
from icon.server.utils.handle_keyboard_interrupt import handle_keyboard_interrupt
from icon.server.utils.pydase_client import client_call_with_timeout

if TYPE_CHECKING:
    import queue

    from icon.server.data_access.experiment_data import DatabaseValueType
    from icon.server.data_access.models.sqlite.device import Device
    from icon.server.hardware_processing.devices import Devices, Hardware
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


def should_divert_task(
    task: HardwareProcessingTask,
    parameter_update_timestamp: datetime | None,
    job_run_status: JobRunStatus,
) -> bool:
    """Whether the hardware worker should divert a task back to pre-processing.

    A paused job always diverts. Otherwise a task is diverted when its parameters
    went stale (it was built before the last parameter update) -- except for realtime
    scans, whose sequences the realtime handler regenerates in place, so diverting a
    stale realtime task would just bounce it back and forth in a tight loop.

    ``parameter_update_timestamp`` is stored without timezone info (as UTC), so it is
    made timezone-aware before comparing with the task's timezone-aware ``created``.
    """
    if job_run_status == JobRunStatus.PAUSED:
        return True
    if contains_realtime_parameter(task.pre_processing_task.scan_parameters):
        return False
    return (
        parameter_update_timestamp is not None
        and task.created < parameter_update_timestamp.replace(tzinfo=UTC)
    )


def run_device(
    device_id: str,
    device: HardwareController,
    instructions: str,
    delay: float = 0.0,
) -> ExperimentDeviceDataPoint:
    """Device run and receive methods intended for execution in a ThreadPoolExecutor.

    The purpose is to delay the run call on the main device until the subordinate is armed.
    """
    if delay:
        time.sleep(delay)
    device.run()
    return ExperimentDeviceDataPoint(
        device_id,
        readouts=device.receive(),
        hardware_instructions=instructions,
    )


class HardwareProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        hardware_processing_queue: queue.PriorityQueue[HardwareProcessingTask],
        post_processing_queue: multiprocessing.Queue[PostProcessingTask],
        manager: SharedResourceManager,
        devices: Devices,
    ) -> None:
        super().__init__()
        self._queue = hardware_processing_queue
        self._post_processing_queue = post_processing_queue
        self._manager = manager
        self._pydase_clients: dict[str, pydase.Client] = {}
        self._executor: ThreadPoolExecutor | None = None
        self._executor_size = 0
        self._main_device_start_delay = get_config().hardware.main_device_start_delay

        self._devices = devices

    def get_device(self, device_id: str) -> Hardware:
        try:
            return self._devices[device_id]
        except KeyError as e:
            raise RuntimeError(
                f"No such device: {e} (the device might have been disabled)"
            ) from None

    def _update_pydase_service_parameter(
        self, device: Device, access_path: str, new_value: DatabaseValueType
    ) -> None:
        client = self._pydase_clients[device.name]
        timeout = get_config().devices.set_value_timeout_seconds
        try:
            client_call_with_timeout(
                client=client,
                event="update_value",
                data={"access_path": access_path, "value": dump(new_value)},
                timeout=timeout,
            )
        except socketio.exceptions.BadNamespaceError as e:
            raise RuntimeError(
                f"Failed to connect to device {device.name!r} as {device.url!r}."
            ) from e
        except socketio.exceptions.TimeoutError as e:
            raise RuntimeError(
                f"Timed out after {timeout} s while setting {access_path!r} of "
                f"device {device.name!r}."
            ) from e

        for attempt in range(1, device.retry_attempts + 1):
            value_on_device = client_call_with_timeout(
                client=client,
                event="get_value",
                data=access_path,
                timeout=timeout,
            )
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

    def _get_executor(self, size: int) -> ThreadPoolExecutor:
        """Returns the device communication thread pool, resized if too small."""
        if self._executor is None or self._executor_size < size:
            if self._executor is not None:
                self._executor.shutdown()
            self._executor_size = max(size, 1)
            self._executor = ThreadPoolExecutor(
                max_workers=self._executor_size, thread_name_prefix="hardware"
            )
        return self._executor

    @staticmethod
    def _send_to_devices(
        hardware_instructions: list[tuple[str, HardwareController, str]],
    ) -> dict[str, RPCResponseError]:
        """Send the hardware instructions, stopping at the first device error.

        Returns:
            The error by device ID, empty if all devices accepted their instructions.
        """
        for device_id, device, instructions in hardware_instructions:
            try:
                device.send(data=instructions)
            except RPCResponseError as e:
                return {device_id: e}
        return {}

    def _start_devices(
        self, hardware_instructions: list[tuple[str, HardwareController, str]]
    ) -> tuple[dict[str, ExperimentDeviceDataPoint], dict[str, RPCResponseError]]:
        """Run the devices in parallel.

        Returns:
            The data of every device that ran successfully, and the errors of
            every device that reported one, by device ID.
        """
        num_devices = len(hardware_instructions)
        executor = self._get_executor(num_devices)
        futures = {
            device_id: executor.submit(
                run_device,
                device_id,
                device,
                instructions,
                delay=self._main_device_start_delay
                if i == 0 and num_devices > 1
                else 0.0,
            )
            for i, (device_id, device, instructions) in enumerate(hardware_instructions)
        }
        wait(futures.values())

        results: dict[str, ExperimentDeviceDataPoint] = {}
        errors: dict[str, RPCResponseError] = {}
        for device_id, future in futures.items():
            try:
                results[device_id] = future.result()
            except RPCResponseError as e:
                errors[device_id] = e
        return results, errors

    def _run_devices(
        self, hardware_instructions: list[tuple[str, HardwareController, str]]
    ) -> tuple[list[ExperimentDeviceDataPoint], RPCResponseError | None]:
        """Send the hardware instructions to the devices, then run them.

        A device that reports an error gets a `HardwareProcessingError` in place of
        its readouts. Devices that did not return readouts because of another
        device's error get empty readouts.

        Returns:
            The data of every device, and the first error reported by a device.
        """
        results: dict[str, ExperimentDeviceDataPoint] = {}
        errors = self._send_to_devices(hardware_instructions)
        if not errors:
            results, errors = self._start_devices(hardware_instructions)

        device_data: list[ExperimentDeviceDataPoint] = []
        for device_id, _, instructions in hardware_instructions:
            if device_id in results:
                device_data.append(results[device_id])
                continue
            readouts: Readouts | HardwareProcessingError = (
                HardwareProcessingError(
                    message=extract_hardware_error_message(errors[device_id])
                )
                if device_id in errors
                else Readouts(result_channels={}, vector_channels={}, shot_channels={})
            )
            device_data.append(
                ExperimentDeviceDataPoint(
                    device_id, readouts=readouts, hardware_instructions=instructions
                )
            )
        return device_data, next(iter(errors.values()), None)

    def _fail_job(self, task: HardwareProcessingTask, error: Exception) -> None:
        logger.error("Error in hardware worker.", exc_info=error)
        try_update_run_by_id(
            run_id=task.pre_processing_task.job_run.id,
            status=JobRunStatus.FAILED,
            log=extract_hardware_error_message(error),
        )

    def _submit_post_processing_task(
        self,
        *,
        task: HardwareProcessingTask,
        timestamp: datetime,
        device_data: list[ExperimentDeviceDataPoint],
    ) -> None:
        experiment_data_point = ExperimentDataPoint(
            index=task.data_point_index,
            scan_params=task.scanned_params,
            device_data=device_data,
            timestamp=timestamp.isoformat(),
        )

        post_processing_task = PostProcessingTask(
            priority=task.priority,
            pre_processing_task=task.pre_processing_task,
            data_point=experiment_data_point,
            src_dir=task.src_dir,
            created=task.created,
        )

        self._post_processing_queue.put(post_processing_task)

    @handle_keyboard_interrupt(logger)
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

            # One fetch covers both checks: the run carries the current status
            # (cancel/pause) and the parameter-update timestamp.
            job_run = JobRunRepository.get_run_by_job_id(
                job_id=task.pre_processing_task.job.id,
            )
            if job_run.status in (JobRunStatus.CANCELLED, JobRunStatus.FAILED):
                task.scan_progress.complete(task.pre_processing_task.job_run.id)
                continue

            if should_divert_task(
                task,
                job_run.parameter_update_timestamp,
                job_run.status,
            ):
                task.outdated_tasks.put(task)
                continue
            try:
                self._set_pydase_service_values(scanned_params=task.scanned_params)

                timestamp = datetime.now(timezone)
                all_hardware_instructions = [
                    (device_id, self.get_device(device_id).controller, instructions)
                    for device_id, instructions in task.hardware_instructions
                ]
                hardware_instructions = [
                    (device_id, device, instructions)
                    for device_id, device, instructions in all_hardware_instructions
                    if isinstance(device, HardwareController)
                ]
                device_data, device_error = self._run_devices(hardware_instructions)

                # Also submitted when a device reported an error, to persist the
                # hardware instructions before the job is marked as failed.
                self._submit_post_processing_task(
                    task=task, timestamp=timestamp, device_data=device_data
                )
                if device_error is not None:
                    self._fail_job(task, device_error)
            except Exception as e:
                self._fail_job(task, e)
            finally:
                task.scan_progress.complete(task.pre_processing_task.job_run.id)
