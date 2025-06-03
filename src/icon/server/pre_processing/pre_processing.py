from __future__ import annotations

import itertools
import logging
import multiprocessing
import os
import queue
import re
import tempfile
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import psutil
import pytz
import socketio  # type: ignore
import tiqi_plugin

from icon.config.config import get_config
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataPoint,
    ExperimentDataRepository,
    ResultDict,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
    ValkeyValueType,
)

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.job import Job
    from icon.server.hardware_processing.task import HardwareProcessingTask
    from icon.server.pre_processing.task import PreProcessingTask
    from icon.server.queue_manager import PriorityQueueManager

DUMMY_DATA = True
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


def get_scan_combinations(job: Job) -> list[dict[str, float]]:
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
        param.variable_id: param.scan_values for param in job.scan_parameters
    }

    # Generate combinations using itertools.product
    keys = list(parameter_values.keys())
    values = [parameter_values[key] for key in keys]
    combinations = itertools.product(*values)

    # Map each combination back to variable IDs
    return [
        dict(zip(keys, combination)) for combination in combinations
    ] * job.repetitions


class PreProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        worker_number: int,
        pre_processing_queue: queue.PriorityQueue[PreProcessingTask],
        hardware_processing_queue: queue.PriorityQueue[HardwareProcessingTask],
        manager: PriorityQueueManager,
    ) -> None:
        super().__init__()
        self._queue = pre_processing_queue
        self._hw_processing_queue = hardware_processing_queue
        self._worker_number = worker_number
        self._manager = manager

    def run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger.debug("%s - Created temp dir %s", self._worker_number, tmp_dir)

            external_sio = socketio.RedisManager(write_only=True, logger=logger)
            while True:
                pre_processing_task = self._queue.get()

                external_sio.emit(
                    "update_job",
                    {
                        "job_id": pre_processing_task.job.id,
                        "updated_properties": {
                            "status": pre_processing_task.job.status.value
                        },
                    },
                )

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

                # cache_local_params(pre_processing_task.timestamp)

                scan_parameter_value_combinations = get_scan_combinations(
                    pre_processing_task.job
                )

                data_points_to_process: queue.Queue[tuple[int, dict[str, float]]] = (
                    self._manager.Queue()
                )
                processed_data_points: queue.Queue[Any] = self._manager.Queue()

                for combination in enumerate(scan_parameter_value_combinations):
                    data_points_to_process.put(combination)

                # store current parameter values to restore them at the end
                prev_param_values: dict[str, ValkeyValueType] = {}
                for key in scan_parameter_value_combinations[-1]:
                    prev_param_values[key] = (
                        ParametersRepository.get_ionpulse_parameter_by_id(key)
                    )
                # logger.info("Current values: %s", prev_param_values)

                experiment_id = re.findall(
                    r"\((.*)\)",
                    pre_processing_task.job.experiment_source.experiment_id,
                )[0]

                if not DUMMY_DATA:
                    client = tiqi_plugin.Client(
                        get_config().ionpulse_plugin.host,
                        get_config().ionpulse_plugin.rpc_port,
                        client_type="rpc",
                    )
                    client.Experiments[
                        experiment_id
                    ].Shots = pre_processing_task.job.number_of_shots

                ExperimentDataRepository.update_metadata_by_job_id(
                    job_id=pre_processing_task.job.id,
                    number_of_shots=pre_processing_task.job.number_of_shots,
                    repetitions=pre_processing_task.job.repetitions,
                    number_of_data_points=len(scan_parameter_value_combinations),
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
                    # TODO: this should probably be done with multiple workers to speed
                    # up the preparation of JSONs
                    try:
                        index, data_point = data_points_to_process.get(block=False)
                    except queue.Empty:
                        time.sleep(0.001)
                        continue

                    global_parameter_timestamp = datetime.now(timezone)
                    # # TODO: create this function
                    # sequence_json = generate_json_sequence()
                    #
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

                    # set scan parameter values
                    ParametersRepository.update_ionpulse_parameters(data_point)  # type: ignore

                    if not DUMMY_DATA:
                        result: ResultDict = cast(
                            "ResultDict",
                            client.Experiments[experiment_id].run(),  # type: ignore
                        )
                    else:
                        import random
                        import statistics

                        shot_channel = random.choices(
                            range(12, 50), k=pre_processing_task.job.number_of_shots
                        )

                        result = {
                            "result_channels": {"ca+": statistics.fmean(shot_channel)},
                            "shot_channels": {"ca+": shot_channel},
                            "vector_channels": {},
                        }

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

                    external_sio.emit(
                        f"experiment_{pre_processing_task.job.id}",
                        experiment_data_point,
                        room=[
                            f"experiment_{pre_processing_task.job.id}",
                        ],
                    )
                external_sio.close_room(f"experiment_{pre_processing_task.job.id}")

                # restore previous values
                ParametersRepository.update_ionpulse_parameters(prev_param_values)

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

                external_sio.emit(
                    "update_job",
                    {
                        "job_id": pre_processing_task.job.id,
                        "updated_properties": {"status": JobStatus.PROCESSED.value},
                    },
                )
