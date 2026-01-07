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
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Self, TypeVar

import psutil
import pytz

import icon.server.utils.git_helpers
from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.scan_parameter import (
    contains_realtime_parameter,
)
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
    from collections.abc import Iterator

    from icon.server.data_access.models.sqlite.job import Job
    from icon.server.pre_processing.task import PreProcessingTask
    from icon.server.shared_resource_manager import SharedResourceManager
    from icon.server.utils.types import UpdateQueue

logger = logging.getLogger(__name__)
timezone = pytz.timezone(get_config().date.timezone)

ScanCombination = frozenset[tuple[str, DatabaseValueType]]


class ParamUpdateMode(str, Enum):
    ALL_UP_TO_DATE = "all_up_to_date"
    ALL_FROM_TIMESTAMP = "all_from_timestamp"
    LOCALS_FROM_TS_GLOBALS_LATEST = "locals_ts_globals_now"
    ONLY_NEW_PARAMETERS = "only_new_parameters"


def prepare_experiment_library_folder(
    src_dir: str, pre_processing_task: PreProcessingTask
) -> None:
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
    parameter_values = {
        scan_param.unique_id(): scan_param.scan_values
        for scan_param in job.scan_parameters
        if not scan_param.realtime
    }

    if not parameter_values:
        return []

    # Generate combinations using itertools.product
    keys, values = zip(*parameter_values.items())

    combinations = itertools.product(*values)

    # Map each combination back to variable IDs
    return [
        dict(zip(keys, combination)) for combination in combinations
    ] * job.repetitions


def parse_experiment_identifier(identifier: str) -> tuple[str, str, str]:
    """
    Parses an experiment identifier and returns:
    - the module path (e.g. 'experiment_library.experiments.exp_name')
    - the experiment class name (e.g. 'ClassName')
    - the experiment instance name (e.g. 'Instance name')

    Example:
        "experiment_library.experiments.exp_name.ClassName (Instance name)"
        -> ("experiment_library.experiments.exp_name", "ClassName", "Instance name")
    """

    match = re.match(r"^(.*)\.([^. ]+) \(([^)]+)\)$", identifier)
    if match:
        return match.group(1), match.group(2), match.group(3)
    raise ValueError("Unexpected format of experiment identifier: ", identifier)


@dataclass(frozen=True)
class ExperimentIdentifier:
    module_name: str
    """Module path (e.g. 'experiment_library.experiments.exp_name')"""
    class_name: str
    """Experiment class name (e.g. 'ClassName')"""
    instance_name: str
    """Experiment instance name (e.g. 'Instance name')"""

    @classmethod
    def from_str(cls, identifier_str: str) -> Self:
        """Parses an experiment identifier and returns:
        - the module path (e.g. 'experiment_library.experiments.exp_name')
        - the experiment class name (e.g. 'ClassName')
        - the experiment instance name (e.g. 'Instance name')

        Example:
            "experiment_library.experiments.exp_name.ClassName (Instance name)"
            -> ("experiment_library.experiments.exp_name", "ClassName", "Instance name")
        """
        match = re.match(r"^(.*)\.([^. ]+) \(([^)]+)\)$", identifier_str)
        if not match:
            raise ValueError(
                "Unexpected format of experiment identifier: ", identifier_str
            )
        return cls(match.group(1), match.group(2), match.group(3))

    def __str__(self) -> str:
        return f"{self.module_name}.{self.class_name}.{self.instance_name}"


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
        # Queues to communicate with the hardware worker:
        self._data_points_to_process: queue.Queue[
            tuple[int, dict[str, DatabaseValueType]]
        ]
        self._processed_data_points: queue.Queue[HardwareProcessingTask]
        self._parameter_dict: dict[str, DatabaseValueType] = {}

    def run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger.debug("Created temporary directory %s", tmp_dir)

            while True:
                pre_processing_task = self._queue.get()

                self._data_points_to_process = self._manager.Queue()
                self._processed_data_points = self._manager.Queue()

                try:
                    self._process_task(pre_processing_task, tmp_dir=tmp_dir)

                    logger.info(
                        "JobRun with id '%s' finished",
                        pre_processing_task.job_run.id,
                    )

                    if (
                        JobRunRepository.get_run_by_job_id(
                            job_id=pre_processing_task.job.id
                        ).status
                        == JobRunStatus.PROCESSING
                    ):
                        JobRunRepository.update_run_by_id(
                            run_id=pre_processing_task.job_run.id,
                            status=JobRunStatus.DONE,
                        )
                except Exception as e:
                    logger.exception(
                        "JobRun with id '%s' failed with error: %s",
                        pre_processing_task.job_run.id,
                        e,
                    )

                    if (
                        JobRunRepository.get_run_by_job_id(
                            job_id=pre_processing_task.job.id
                        ).status
                        == JobRunStatus.PROCESSING
                    ):
                        JobRunRepository.update_run_by_id(
                            run_id=pre_processing_task.job_run.id,
                            status=JobRunStatus.FAILED,
                            log=str(e),
                        )
                finally:
                    JobRepository.update_job_status(
                        job=pre_processing_task.job, status=JobStatus.PROCESSED
                    )

    def _process_task(
        self, pre_processing_task: PreProcessingTask, tmp_dir: str
    ) -> None:
        job = pre_processing_task.job
        JobRunRepository.update_run_by_id(
            run_id=pre_processing_task.job_run.id,
            status=JobRunStatus.PROCESSING,
        )

        namespace = ExperimentIdentifier.from_str(job.experiment_source.experiment_id)
        # empty update queue
        self._handle_parameter_updates(pre_processing_task, namespace=namespace)

        if job_run_cancelled_or_failed(
            job_id=job.id,
        ):
            return

        change_process_priority(pre_processing_task.priority)

        src_dir = source_dir(debug_mode=pre_processing_task.debug_mode, tmp_dir=tmp_dir)

        prepare_experiment_library_folder(
            src_dir=src_dir,
            pre_processing_task=pre_processing_task,
        )

        self._update_parameter_dict(pre_processing_task, namespace)

        readout_metadata = asyncio.run(
            PycrystalLibraryRepository.get_experiment_readout_metadata(
                exp_module_name=namespace.module_name,
                exp_instance_name=namespace.instance_name,
                parameter_dict=self._parameter_dict,
            )
        )

        ExperimentDataRepository.update_metadata_by_job_id(
            job_id=job.id,
            number_of_shots=job.number_of_shots,
            repetitions=job.repetitions,
            parameters=job.scan_parameters,
            readout_metadata=readout_metadata,
        )

        if contains_realtime_parameter(job.scan_parameters):
            self._handle_realtime_scan(
                pre_processing_task, src_dir=src_dir, namespace=namespace
            )
        else:
            self._handle_regular_scan(
                pre_processing_task, src_dir=src_dir, namespace=namespace
            )

    def _update_parameter_dict(
        self,
        pre_processing_task: PreProcessingTask,
        namespace: ExperimentIdentifier,
        new_parameters: dict[str, DatabaseValueType] | None = None,
        mode: ParamUpdateMode = ParamUpdateMode.LOCALS_FROM_TS_GLOBALS_LATEST,
    ) -> None:
        """Update self._parameter_dict according to the requested mode.

        Args:
            new_parameters: Dictionary containing parameter IDs and corresponding
                values. If set to None, the whole parameter dict will be updated with
                values from the database. Defaults to None.
            mode: parameter update mode. One of:
                  1) ALL_UP_TO_DATE: locals & globals from latest
                  2) ALL_FROM_TIMESTAMP: locals & globals from local_params_timestamp
                  3) LOCALS_FROM_TS_GLOBALS_LATEST: locals from local_params_timestamp,
                    globals latest (default)
                  4) ONLY_NEW_PARAMETERS: only merge `new_parameters`, no DB queries
        """

        self._global_parameter_timestamp = datetime.now(timezone)

        if mode == ParamUpdateMode.ONLY_NEW_PARAMETERS:
            if new_parameters:
                self._parameter_dict.update(new_parameters)
            ExperimentDataRepository.write_parameter_update_by_job_id(
                job_id=pre_processing_task.job.id,
                timestamp=self._global_parameter_timestamp.isoformat(),
                parameter_values=self._parameter_dict,
            )
            return

        if mode == ParamUpdateMode.ALL_UP_TO_DATE:
            locals_before = None
            globals_before = None
        elif mode == ParamUpdateMode.ALL_FROM_TIMESTAMP:
            locals_before = pre_processing_task.local_parameters_timestamp
            globals_before = pre_processing_task.local_parameters_timestamp
        elif mode == ParamUpdateMode.LOCALS_FROM_TS_GLOBALS_LATEST:
            locals_before = pre_processing_task.local_parameters_timestamp
            globals_before = None

        global_values = ParametersRepository.get_influxdb_parameters(
            before=globals_before,
        )
        local_values = ParametersRepository.get_influxdb_parameters(
            before=locals_before,
            namespace=str(namespace),
        )

        self._parameter_dict = {**self._parameter_dict, **global_values, **local_values}

        ExperimentDataRepository.write_parameter_update_by_job_id(
            job_id=pre_processing_task.job.id,
            timestamp=self._global_parameter_timestamp.isoformat(),
            parameter_values=self._parameter_dict,
        )

    def _handle_parameter_updates(
        self, pre_processing_task: PreProcessingTask, namespace: ExperimentIdentifier
    ) -> None:
        for parameter_update in consume_queue(self._update_queue):
            event = parameter_update["event"]
            job_id = parameter_update.get("job_id", None)
            new_parameters = parameter_update.get("new_parameters", None)

            if event == "update_parameters" and (
                job_id is None or job_id == pre_processing_task.job.id
            ):
                self._update_parameter_dict(
                    pre_processing_task, namespace, mode=ParamUpdateMode.ALL_UP_TO_DATE
                )
            elif event == "calibration" and new_parameters is not None:
                self._update_parameter_dict(
                    pre_processing_task,
                    namespace,
                    new_parameters=new_parameters,
                    mode=ParamUpdateMode.ONLY_NEW_PARAMETERS,
                )

    def _submit_task_to_hw_worker(
        self,
        *,
        task: HardwareProcessingTask,
    ) -> None:
        logger.debug(
            "Submitting data point %s (job_run_id=%s)",
            task.data_point_index,
            task.pre_processing_task.job_run.id,
        )
        self._hw_processing_queue.put(task)

    def _handle_regular_scan(
        self,
        pre_processing_task: PreProcessingTask,
        namespace: ExperimentIdentifier,
        src_dir: str,
    ) -> None:
        scan_parameter_value_combinations = get_scan_combinations(
            pre_processing_task.job
        )
        for combination in enumerate(scan_parameter_value_combinations):
            self._data_points_to_process.put(combination)

        while self._processed_data_points.qsize() != len(
            scan_parameter_value_combinations
        ):
            self._handle_parameter_updates(pre_processing_task, namespace)

            # TODO: this should probably be done with multiple workers to
            # speed up the preparation of JSONs
            try:
                index, data_point = self._data_points_to_process.get(block=False)
            except queue.Empty:
                time.sleep(0.001)
                continue

            if job_run_cancelled_or_failed(
                job_id=pre_processing_task.job.id,
            ):
                break

            self._submit_task_to_hw_worker(
                task=self._create_hardware_task(
                    pre_processing_task=pre_processing_task,
                    index=index,
                    data_point=data_point,
                    sequence_json=generate_sequence_json(
                        n_shots=pre_processing_task.job.number_of_shots,
                        parameter_dict={**self._parameter_dict, **data_point},
                        namespace=namespace,
                    ),
                    src_dir=src_dir,
                )
            )

    def _create_hardware_task(
        self,
        *,
        pre_processing_task: PreProcessingTask,
        index: int,
        data_point: dict[str, DatabaseValueType],
        sequence_json: str,
        src_dir: str,
    ) -> HardwareProcessingTask:
        return HardwareProcessingTask(
            data_point_index=index,
            pre_processing_task=pre_processing_task,
            priority=pre_processing_task.priority,
            global_parameter_timestamp=self._global_parameter_timestamp,
            scanned_params=data_point,
            src_dir=src_dir,
            sequence_json=sequence_json,
            processed_data_points=self._processed_data_points,
            data_points_to_process=self._data_points_to_process,
            created=datetime.now(timezone),
        )

    def _handle_realtime_scan(
        self,
        pre_processing_task: PreProcessingTask,
        namespace: ExperimentIdentifier,
        src_dir: str,
    ) -> None:
        params = pre_processing_task.job.scan_parameters
        realtime_param = next(p for p in params if p.realtime)
        n_scan_values = len(realtime_param.scan_values)

        hardware_tasks: dict[ScanCombination, HardwareProcessingTask] = {}

        realtime_scan_counter = itertools.count()
        # n_scan_values iterations if n_scan_values > 0
        # ∞ iterations if n_scan_values == 0
        times = (n_scan_values,) if n_scan_values > 0 else ()
        for _ in itertools.repeat(None, *times):
            for combination in get_scan_combinations(pre_processing_task.job):
                self._data_points_to_process.put(
                    (next(realtime_scan_counter), combination)
                )
            if self._data_points_to_process.qsize() == 0:
                self._data_points_to_process.put((next(realtime_scan_counter), {}))
            for index, data_point in consume_queue(self._data_points_to_process):
                if job_run_cancelled_or_failed(
                    job_id=pre_processing_task.job.id,
                ):
                    return
                self._handle_parameter_updates(pre_processing_task, namespace=namespace)
                frozen_data_point = freeze_dict(data_point)
                hardware_task = hardware_tasks.get(frozen_data_point)
                if (
                    hardware_task is None
                    or hardware_task.global_parameter_timestamp
                    < self._global_parameter_timestamp
                ):
                    hardware_task = self._create_hardware_task(
                        pre_processing_task=pre_processing_task,
                        index=index,
                        data_point=data_point,
                        sequence_json=generate_sequence_json(
                            n_shots=pre_processing_task.job.number_of_shots,
                            parameter_dict={**self._parameter_dict, **data_point},
                            namespace=namespace,
                        ),
                        src_dir=src_dir,
                    )
                    hardware_tasks[frozen_data_point] = hardware_task
                hardware_task.created = datetime.now(timezone)
                hardware_task.data_point_index = index
                self._submit_task_to_hw_worker(task=hardware_task)


T = TypeVar("T")


def consume_queue(q: multiprocessing.Queue[T] | queue.Queue[T]) -> Iterator[T]:
    while True:
        try:
            yield q.get(block=False)
        except queue.Empty:
            return


def freeze_dict(combination: dict[str, DatabaseValueType]) -> ScanCombination:
    return frozenset(combination.items())


def source_dir(*, debug_mode: bool, tmp_dir: str) -> str:
    if (experiment_library_dir := get_config().experiment_library.dir) is None:
        raise RuntimeError("Config: experiment_library.dir is not defined")

    return experiment_library_dir if debug_mode else tmp_dir


def generate_sequence_json(
    n_shots: int,
    parameter_dict: dict[str, DatabaseValueType],
    namespace: ExperimentIdentifier,
) -> str:
    return asyncio.run(
        PycrystalLibraryRepository.generate_json_sequence(
            n_shots=n_shots,
            parameter_dict=parameter_dict,
            exp_module_name=namespace.module_name,
            exp_instance_name=namespace.instance_name,
        )
    )
