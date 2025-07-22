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
import pytz

from icon.config.config import get_config
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataRepository,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
    job_run_cancelled_or_failed,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
from icon.server.data_access.repositories.pycrystal_library_repository import (
    PycrystalLibraryRepository,
)
from icon.server.hardware_processing.task import HardwareProcessingTask

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.models.sqlite.job import Job
    from icon.server.pre_processing.task import PreProcessingTask
    from icon.server.shared_resource_manager import SharedResourceManager
    from icon.server.utils.types import UpdateQueue

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

    if os.getuid() == 0:
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

    if values == []:
        return []

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


class PreProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        worker_number: int,
        pre_processing_queue: queue.PriorityQueue[PreProcessingTask],
        update_queue: multiprocessing.Queue[UpdateQueue],
        hardware_processing_queue: queue.PriorityQueue[HardwareProcessingTask],
        manager: SharedResourceManager,
    ) -> None:
        super().__init__()
        self._queue = pre_processing_queue
        self._update_queue = update_queue
        self._hw_processing_queue = hardware_processing_queue
        self._worker_number = worker_number
        self._manager = manager
        self._data_points_to_process: queue.Queue[
            tuple[int, dict[str, DatabaseValueType]]
        ]
        self._processed_data_points: queue.Queue[HardwareProcessingTask]
        self._pre_processing_task: PreProcessingTask
        self._src_dir: str
        self._exp_module_name: str
        self._exp_class_name: str
        self._experiment_id: str
        self._scan_parameter_value_combinations: list[dict[str, DatabaseValueType]]
        self._parameter_dict: dict[str, DatabaseValueType] = {}

    def run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger.debug("Created temporary directory %s", tmp_dir)

            while True:
                self._pre_processing_task = self._queue.get()
                # empty update queue
                self._handle_parameter_updates()

                self._data_points_to_process = self._manager.Queue()
                self._processed_data_points = self._manager.Queue()

                try:
                    ExperimentDataRepository.update_metadata_by_job_id(
                        job_id=self._pre_processing_task.job.id,
                        number_of_shots=self._pre_processing_task.job.number_of_shots,
                        repetitions=self._pre_processing_task.job.repetitions,
                        parameters=self._pre_processing_task.job.scan_parameters,
                    )

                    if job_run_cancelled_or_failed(
                        job_id=self._pre_processing_task.job.id,
                    ):
                        continue

                    JobRunRepository.update_run_by_id(
                        run_id=self._pre_processing_task.job_run.id,
                        status=JobRunStatus.PROCESSING,
                    )

                    change_process_priority(self._pre_processing_task.priority)

                    self._src_dir = (
                        get_config().experiment_library.dir
                        if self._pre_processing_task.debug_mode
                        else tmp_dir
                    )

                    prepare_experiment_library_folder(
                        src_dir=self._src_dir,
                        pre_processing_task=self._pre_processing_task,
                    )

                    self._exp_module_name, self._exp_class_name, self._experiment_id = (
                        parse_experiment_identifier(
                            self._pre_processing_task.job.experiment_source.experiment_id
                        )
                    )

                    self._update_parameter_dict()

                    self._scan_parameter_value_combinations = get_scan_combinations(
                        self._pre_processing_task.job
                    )

                    if len(self._scan_parameter_value_combinations) > 0:
                        self._handle_regular_scan()
                    else:
                        self._handle_continuous_scan()

                    logger.info(
                        "JobRun with id '%s' finished",
                        self._pre_processing_task.job_run.id,
                    )

                    if (
                        JobRunRepository.get_run_by_job_id(
                            job_id=self._pre_processing_task.job.id
                        ).status
                        == JobRunStatus.PROCESSING
                    ):
                        JobRunRepository.update_run_by_id(
                            run_id=self._pre_processing_task.job_run.id,
                            status=JobRunStatus.DONE,
                        )

                except Exception as e:
                    logger.exception(
                        "JobRun with id '%s' failed with error: %s",
                        self._pre_processing_task.job_run.id,
                        e,
                    )

                    if (
                        JobRunRepository.get_run_by_job_id(
                            job_id=self._pre_processing_task.job.id
                        ).status
                        == JobRunStatus.PROCESSING
                    ):
                        JobRunRepository.update_run_by_id(
                            run_id=self._pre_processing_task.job_run.id,
                            status=JobRunStatus.FAILED,
                            log=str(e),
                        )
                finally:
                    JobRepository.update_job_status(
                        job=self._pre_processing_task.job, status=JobStatus.PROCESSED
                    )

    def _update_parameter_dict(
        self,
        new_parameters: dict[str, DatabaseValueType] | None = None,
        update_all: bool = False,
    ) -> None:
        """Updates self._parameter_dict.

        Args:
            new_parameters: Dictionary containing parameter IDs and corresponding
                values. If set to None, the whole parameter dict will be updated with
                values from the database. Defaults to None.
            update_all: If True (and new_parameters is None), updates both local
                (experiment) parameters and global parameters with the latest values. If
                False, cache the latest global parameter values and the local
                (experiment) parameter values before the local_params_timestamp from the
                database job entry.
        """

        self._global_parameter_timestamp = datetime.now(timezone)

        if new_parameters is not None:
            self._parameter_dict.update(new_parameters)

        else:
            if update_all:
                local_params_timestamp = self._global_parameter_timestamp.isoformat()
            else:
                local_params_timestamp = (
                    self._pre_processing_task.local_parameters_timestamp
                )

            self._parameter_dict = cache_parameter_values(
                local_params_timestamp=local_params_timestamp,
                namespace=f"{self._exp_module_name}.{self._exp_class_name}",
            )

        ExperimentDataRepository.write_parameter_update_by_job_id(
            job_id=self._pre_processing_task.job.id,
            timestamp=self._global_parameter_timestamp.isoformat(),
            parameter_values=self._parameter_dict,
        )

    def _handle_parameter_updates(self) -> None:
        done = False

        while not done:
            try:
                parameter_update = self._update_queue.get(block=False)

                event = parameter_update["event"]
                job_id = parameter_update.get("job_id", None)
                new_parameters = parameter_update.get("new_parameters", None)

                if event == "update_parameters" and (
                    job_id is None or job_id == self._pre_processing_task.job.id
                ):
                    self._update_parameter_dict(update_all=True)
                elif event == "calibration" and new_parameters is not None:
                    self._update_parameter_dict(
                        update_all=True, new_parameters=new_parameters
                    )

            except queue.Empty:
                done = True

    def _get_sequence_json(self, parameter_dict: dict[str, DatabaseValueType]) -> str:
        return asyncio.run(
            PycrystalLibraryRepository.generate_json_sequence(
                parameter_dict=parameter_dict,
                exp_module_name=self._exp_module_name,
                exp_instance_name=self._experiment_id,
            )
        )

    def _submit_data_point_to_hw_worker(
        self,
        *,
        index: int,
        data_point: dict[str, DatabaseValueType],
        sequence_json: str,
    ) -> None:
        task = HardwareProcessingTask(
            data_point_index=index,
            pre_processing_task=self._pre_processing_task,
            priority=self._pre_processing_task.priority,
            global_parameter_timestamp=self._global_parameter_timestamp,
            scanned_params=data_point,
            src_dir=self._src_dir,
            sequence_json=sequence_json,
            processed_data_points=self._processed_data_points,
            data_points_to_process=self._data_points_to_process,
            created=datetime.now(timezone),
        )

        logger.debug(
            "Submitting data point %s (job_run_id=%s)",
            index,
            self._pre_processing_task.job_run.id,
        )
        self._hw_processing_queue.put(task)

    def _handle_regular_scan(self) -> None:
        for combination in enumerate(self._scan_parameter_value_combinations):
            self._data_points_to_process.put(combination)

        while self._processed_data_points.qsize() != len(
            self._scan_parameter_value_combinations
        ):
            self._handle_parameter_updates()

            # TODO: this should probably be done with multiple workers to
            # speed up the preparation of JSONs
            try:
                index, data_point = self._data_points_to_process.get(block=False)
            except queue.Empty:
                time.sleep(0.001)
                continue

            if job_run_cancelled_or_failed(
                job_id=self._pre_processing_task.job.id,
            ):
                break

            sequence_json = self._get_sequence_json(
                parameter_dict={**self._parameter_dict, **data_point}
            )

            self._submit_data_point_to_hw_worker(
                index=index, data_point=data_point, sequence_json=sequence_json
            )

    def _handle_continuous_scan(self) -> None:
        sequence_json = self._get_sequence_json(parameter_dict=self._parameter_dict)

        continuous_scan_index = 0

        for index in range(2):
            self._submit_data_point_to_hw_worker(
                index=index, data_point={}, sequence_json=sequence_json
            )
            continuous_scan_index += 1

        while not job_run_cancelled_or_failed(
            job_id=self._pre_processing_task.job.id,
        ):
            if self._data_points_to_process.qsize() != 0:
                raise Exception("Something went wrong")

            self._handle_parameter_updates()

            try:
                hw_task = self._processed_data_points.get(block=False)
            except queue.Empty:
                time.sleep(0.1)
                continue

            if hw_task.global_parameter_timestamp < self._global_parameter_timestamp:
                sequence_json = self._get_sequence_json(
                    parameter_dict=self._parameter_dict
                )
            else:
                sequence_json = hw_task.sequence_json

            self._submit_data_point_to_hw_worker(
                index=continuous_scan_index,
                data_point={},
                sequence_json=sequence_json,
            )
            continuous_scan_index += 1
