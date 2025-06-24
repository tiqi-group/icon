from __future__ import annotations

import asyncio
import itertools
import logging
import multiprocessing
import os
import queue
import re
import tempfile
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

import psutil
import pydase
import pytz

from icon.config.config import get_config
from icon.server.data_access.models.enums import DeviceStatus, JobRunStatus, JobStatus
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataPoint,
    ExperimentDataRepository,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
from icon.server.data_access.repositories.pycrystal_library_repository import (
    PycrystalLibraryRepository,
)
from icon.server.hardware_processing.hardware_controller import HardwareController

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.models.sqlite.job import Job
    from icon.server.hardware_processing.task import HardwareProcessingTask
    from icon.server.pre_processing.task import PreProcessingTask
    from icon.server.shared_resource_manager import SharedResourceManager

logger = logging.getLogger(__name__)
timezone = pytz.timezone(get_config().date.timezone)


def prepare_experiment_library_folder(
    src_dir: str, pre_processing_task: PreProcessingTask
) -> None:
    import icon.server.utils.git_helpers

    if not icon.server.utils.git_helpers.local_repo_exists(
        repository_dir=src_dir,
        repository=get_config().experiment_library.git_repository,
    ):
        icon.server.utils.git_helpers.git_clone(
            repository=get_config().experiment_library.git_repository,
            dir=src_dir,
        )

    icon.server.utils.git_helpers.checkout_commit(
        git_hash=pre_processing_task.git_commit_hash, cwd=src_dir
    )
    # update_python_environment(src_dir)


def change_process_priority(priority: int) -> None:
    """Changes process priority. Only superusers can decrease the niceness of a
    process."""

    p = psutil.Process(os.getpid())

    p.nice(priority)


def get_scan_combinations(job: Job) -> list[dict[str, DatabaseValueType]]:
    """Generates all combinations of scan parameters for a given job. Repeats each
    combination `job.repetitions` times.

    Args:
        job:
            The job containing scan parameters.

    Returns:
        A list of dictionaries, where each dictionary represents a combination of
        parameter values.
    """

    # Extract variable IDs and their scan values from the job's scan parameters
    parameter_values: dict[str, Any] = {}
    for scan_param in job.scan_parameters:
        parameter_values[scan_param.unique_id()] = scan_param.scan_values

    # Generate combinations using itertools.product
    keys = list(parameter_values.keys())
    values = [parameter_values[key] for key in keys]
    combinations = itertools.product(*values)

    # Map each combination back to variable IDs
    return [
        dict(zip(keys, combination)) for combination in combinations
    ] * job.repetitions


def parse_experiment_identifier(identifier: str) -> tuple[str, str, str]:
    """
    Parses an experiment identifier and returns:
    - the module path (e.g. 'experiment_library.experiments.exp_name')
    - the experiment instance name (e.g. 'Instance name')

    Example:
        "experiment_library.experiments.exp_name.ClassName (Instance name)"
        -> ("experiment_library.experiments.exp_name", "Instance name")
    """
    match = re.match(r"^(.*)\.([^. ]+) \(([^)]+)\)$", identifier)
    if match:
        return match.group(1), match.group(2), match.group(3)
    raise ValueError("Unexpected format of experiment identifier: ", identifier)


def cache_parameter_values(
    local_params_timestamp: str, namespace: str
) -> dict[str, DatabaseValueType]:
    parameter_dict: dict[str, DatabaseValueType] = {}
    parameter_dict.update(ParametersRepository.get_influxdbv1_parameters())
    parameter_dict.update(
        ParametersRepository.get_influxdbv1_parameters(
            before=local_params_timestamp,
            namespace=namespace,
        )
    )
    return parameter_dict


def job_run_cancelled_or_failed(job_id: int) -> bool:
    job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
    if job_run.status in (JobRunStatus.CANCELLED, JobRunStatus.FAILED):
        logger.info(
            "JobRun with id %s %s. Discarding data point.",
            job_run.id,
            job_run.status.value,
        )
        return True
    return False


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


class PreProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        worker_number: int,
        pre_processing_queue: queue.PriorityQueue[PreProcessingTask],
        update_queue: multiprocessing.Queue[dict[str, Any]],
        hardware_processing_queue: queue.PriorityQueue[HardwareProcessingTask],
        manager: SharedResourceManager,
    ) -> None:
        super().__init__()
        self._queue = pre_processing_queue
        self._update_queue = update_queue
        self._hw_processing_queue = hardware_processing_queue
        self._worker_number = worker_number
        self._manager = manager

    def run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger.debug("%s - Created temp dir %s", self._worker_number, tmp_dir)

            hardware_controller = HardwareController()
            self._pydase_clients = {
                device.name: pydase.Client(url=device.url, auto_update_proxy=False)
                for device in DeviceRepository.get_devices_by_status(
                    status=DeviceStatus.ENABLED
                )
            }

            while True:
                pre_processing_task = self._queue.get()

                JobRunRepository.update_run_by_id(
                    run_id=pre_processing_task.job_run.id,
                    status=JobRunStatus.PROCESSING,
                )

                # adapt the priority of the pre-processing worker according to the
                # priority of the task. This only works when run as root (uid=0).
                if os.getuid() == 0:
                    change_process_priority(pre_processing_task.priority)

                src_dir = (
                    get_config().experiment_library.dir
                    if pre_processing_task.debug_mode
                    else tmp_dir
                )

                prepare_experiment_library_folder(
                    src_dir=src_dir, pre_processing_task=pre_processing_task
                )

                exp_module_name, exp_class_name, experiment_id = (
                    parse_experiment_identifier(
                        pre_processing_task.job.experiment_source.experiment_id
                    )
                )

                parameter_dict = cache_parameter_values(
                    local_params_timestamp=pre_processing_task.local_parameters_timestamp,
                    namespace=f"{exp_module_name}.{exp_class_name}",
                )

                scan_parameter_value_combinations = get_scan_combinations(
                    pre_processing_task.job
                )

                data_points_to_process: queue.Queue[
                    tuple[int, dict[str, DatabaseValueType]]
                ] = self._manager.Queue()
                processed_data_points: queue.Queue[Any] = self._manager.Queue()

                for combination in enumerate(scan_parameter_value_combinations):
                    data_points_to_process.put(combination)

                ExperimentDataRepository.update_metadata_by_job_id(
                    job_id=pre_processing_task.job.id,
                    number_of_shots=pre_processing_task.job.number_of_shots,
                    repetitions=pre_processing_task.job.repetitions,
                    parameters=pre_processing_task.job.scan_parameters,
                )

                # Prepare and execute data points as long as the number of processed
                # data points does not correspond to the number of scan parameter
                # combinations.
                #
                # TODO: When scanning time, the post-processing worker should put the
                # data points back into the data_points_to_process queue instead of the
                # processed_data_points queue.
                while processed_data_points.qsize() != len(
                    scan_parameter_value_combinations
                ):
                    if job_run_cancelled_or_failed(job_id=pre_processing_task.job.id):
                        break

                    # TODO: this should probably be done with multiple workers to speed
                    # up the preparation of JSONs
                    try:
                        index, data_point = data_points_to_process.get(block=False)
                    except queue.Empty:
                        time.sleep(0.001)
                        continue

                    global_parameter_timestamp = datetime.now(timezone)
                    sequence_json = asyncio.run(
                        PycrystalLibraryRepository.generate_json_sequence(
                            parameter_dict={**parameter_dict, **data_point},
                            exp_module_name=exp_module_name,
                            exp_instance_name=experiment_id,
                        )
                    )

                    # task = HardwareProcessingTask(
                    #     pre_processing_task=pre_processing_task,
                    #     priority=pre_processing_task.priority,
                    #     data_point=data_point,
                    #     global_parameter_timestamp=global_parameter_timestamp,
                    #     src_dir=src_dir,
                    #     sequence_json=sequence_json,
                    # )
                    #
                    # logger.debug(
                    #     "(worker=%s) Submitting data point %s (job_run_id=%s)",
                    #     self._worker_number,
                    #     data_point,
                    #     pre_processing_task.job_run.id,
                    # )
                    # self._hw_processing_queue.put(task)

                    for param, value in data_point.items():
                        device_name, access_path = parse_parameter_id(param_id=param)
                        if device_name is not None:
                            client = self._pydase_clients.get(device_name, None)
                            if client is None:
                                client = pydase.Client(
                                    url=DeviceRepository.get_device_by_name(
                                        name=device_name
                                    ).url,
                                    auto_update_proxy=False,
                                )
                                self._pydase_clients[device_name] = client
                            client.update_value(
                                access_path=access_path, new_value=value
                            )

                    result = hardware_controller.run(
                        sequence=sequence_json,
                        number_of_shots=pre_processing_task.job.number_of_shots,
                    )

                    experiment_data_point: ExperimentDataPoint = {
                        "index": index,
                        "scan_params": data_point,
                        "result_channels": result["result_channels"],
                        "shot_channels": result["shot_channels"],
                        "vector_channels": result["vector_channels"],
                        "timestamp": global_parameter_timestamp.isoformat(),
                    }

                    ExperimentDataRepository.write_experiment_data_by_job_id(
                        job_id=pre_processing_task.job.id,
                        data_point=experiment_data_point,
                    )
                    processed_data_points.put(data_point)

                logger.info(
                    "(worker=%s) JobRun with id '%s' finished",
                    self._worker_number,
                    pre_processing_task.job_run.id,
                )

                JobRepository.update_job_status(
                    job=pre_processing_task.job, status=JobStatus.PROCESSED
                )
                JobRunRepository.update_run_by_id(
                    run_id=pre_processing_task.job_run.id,
                    status=JobRunStatus.DONE,
                )
