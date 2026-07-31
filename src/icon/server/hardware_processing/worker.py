from __future__ import annotations

import json
import logging
import multiprocessing
import re
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pydase
import pytz
import socketio.exceptions
from pydase.utils.serialization.serializer import dump

from icon.config.config import get_config
from icon.server.data_access.models.enums import DeviceStatus, JobRunStatus
from icon.server.data_access.models.sqlite.scan_parameter import (
    contains_realtime_parameter,
)
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.repositories.experiment_data_repository import (
    DeviceSnapshot,
    ExperimentDataPoint,
    ExperimentDataRepository,
)
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.hardware_processing.utils import extract_hardware_error_message
from icon.server.post_processing.task import PostProcessingTask
from icon.server.utils.handle_keyboard_interrupt import handle_keyboard_interrupt
from icon.server.utils.pydase_client import client_call_with_timeout, raw_client_call

if TYPE_CHECKING:
    import queue

    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.models.sqlite.device import Device
    from icon.server.hardware_processing.hardware_controller import HardwareController
    from icon.server.hardware_processing.task import HardwareProcessingTask
    from icon.server.shared_resource_manager import SharedResourceManager

logger = logging.getLogger(__name__)
timezone = pytz.timezone(get_config().date.timezone)

DEVICE_SNAPSHOT_TIMEOUT_SECONDS = 30
"""Timeout for fetching the full state of a device for the HDF5 snapshot."""


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


class HardwareProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        hardware_processing_queue: queue.PriorityQueue[HardwareProcessingTask],
        post_processing_queue: multiprocessing.Queue[PostProcessingTask],
        manager: SharedResourceManager,
        hardware_controller: HardwareController,
    ) -> None:
        super().__init__()
        self._queue = hardware_processing_queue
        self._post_processing_queue = post_processing_queue
        self._manager = manager
        self._pydase_clients: dict[str, pydase.Client] = {}
        self._snapshotted_job_ids: set[int] = set()

        self._hardware_controller = hardware_controller

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

    def _snapshot_connected_devices(self, job_id: int) -> None:
        """Save the full state of all enabled devices to the job's HDF5 file.

        Fetches a fresh serialization from each device and stores it under the
        'devices' group. Unreachable devices are recorded with an error message
        instead of failing the measurement.
        """
        snapshots: list[DeviceSnapshot] = []
        for device in DeviceRepository.get_devices_by_status(
            status=DeviceStatus.ENABLED
        ):
            if device.name not in self._pydase_clients:
                # Non-blocking on purpose: an unreachable device must not stall
                # the snapshot (or the measurement).
                self._pydase_clients[device.name] = pydase.Client(
                    url=device.url,
                    client_id="icon-hardware-worker",
                    block_until_connected=False,
                    auto_update_proxy=False,
                )
            client = self._pydase_clients[device.name]
            timestamp = datetime.now(timezone).isoformat()
            try:
                state = raw_client_call(
                    client,
                    "service_serialization",
                    None,
                    DEVICE_SNAPSHOT_TIMEOUT_SECONDS,
                )
                snapshots.append(
                    DeviceSnapshot(
                        name=device.name,
                        url=device.url,
                        timestamp=timestamp,
                        state_json=json.dumps(state),
                    )
                )
            except Exception as e:
                logger.warning(
                    "Could not fetch state of device %r at %r for job %d: %s",
                    device.name,
                    device.url,
                    job_id,
                    e,
                )
                snapshots.append(
                    DeviceSnapshot(
                        name=device.name,
                        url=device.url,
                        timestamp=timestamp,
                        state_json=None,
                        error=str(e),
                    )
                )

        if snapshots:
            ExperimentDataRepository.write_device_snapshots_by_job_id(
                job_id=job_id, snapshots=snapshots
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
                task.processed_data_points.put(task)
                continue

            if should_divert_task(
                task,
                job_run.parameter_update_timestamp,
                job_run.status,
            ):
                task.outdated_tasks.put(task)
                continue

            job_id = task.pre_processing_task.job.id
            if job_id not in self._snapshotted_job_ids:
                self._snapshotted_job_ids.add(job_id)
                try:
                    self._snapshot_connected_devices(job_id=job_id)
                except Exception:
                    logger.exception(
                        "Failed to write device snapshots for job %d", job_id
                    )

            try:
                self._set_pydase_service_values(scanned_params=task.scanned_params)

                timestamp = datetime.now(timezone)
                self._hardware_controller.send(data=task.sequence_json.encode("utf-8"))
                self._hardware_controller.run()
                result = self._hardware_controller.receive()

                experiment_data_point = ExperimentDataPoint(
                    index=task.data_point_index,
                    scan_params=task.scanned_params,
                    result_channels=result.result_channels,
                    shot_channels=result.shot_channels,
                    vector_channels=result.vector_channels,
                    timestamp=timestamp.isoformat(),
                    sequence_json=task.sequence_json,
                )

                post_processing_task = PostProcessingTask(
                    priority=task.priority,
                    pre_processing_task=task.pre_processing_task,
                    data_point=experiment_data_point,
                    src_dir=task.src_dir,
                    created=task.created,
                )

                self._post_processing_queue.put(post_processing_task)
            except Exception as e:
                logger.exception("pydase error")
                JobRunRepository.update_run_by_id(
                    run_id=task.pre_processing_task.job_run.id,
                    status=JobRunStatus.FAILED,
                    log=extract_hardware_error_message(e),
                )
            finally:
                task.processed_data_points.put(task)
