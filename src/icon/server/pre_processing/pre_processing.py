import logging
import multiprocessing
import queue
import tempfile
from typing import TYPE_CHECKING

# import icon.server.utils.git_helpers
from icon.server.data_access.models.enums import JobIterationStatus
from icon.server.data_access.repositories.job_iteration_repository import (
    JobIterationRepository,
)
from icon.server.pre_processing.task import PreProcessingTask

if TYPE_CHECKING:
    from icon.server.queue_manager import PriorityQueueManager

logger = logging.getLogger(__name__)


DataPoint = int


# def prepare_experiment_library_folder(
#     src_dir: str, pre_processing_task: PreProcessingTask
# ) -> None:
#     if not icon.server.utils.git_helpers.local_repo_exists(
#         repository_dir=src_dir,
#         repository=ServiceConfig(
#             config_sources=FileSource(Path("config/experiment_library.yaml"))
#         ).experiment_library_repository,
#     ):
#         icon.server.utils.git_helpers.git_clone(
#             repository=ServiceConfig(
#                 config_sources=FileSource(Path("config/experiment_library.yaml"))
#             ).experiment_library_repository,
#             dir=src_dir,
#         )
#
#     icon.server.utils.git_helpers.checkout_commit(
#         git_hash=pre_processing_task.git_commit_hash, cwd=src_dir
#     )
#     # update_python_environment(src_dir)


class PreProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        worker_number: int,
        pre_processing_queue: queue.PriorityQueue[PreProcessingTask],
        manager: "PriorityQueueManager",
    ) -> None:
        super().__init__()
        self._queue = pre_processing_queue
        self._worker_number = worker_number
        self._manager = manager

    def run(self) -> None:
        with tempfile.TemporaryDirectory() as dir:
            logger.debug("%s - Created temp dir %s", self._worker_number, dir)

            while True:
                pre_processing_task = self._queue.get()
                JobIterationRepository.update_iteration_by_id(
                    iteration_id=pre_processing_task.iteration_id,
                    status=JobIterationStatus.PROCESSING,
                )

                # no_data_points: int = ...
                # data_points_to_process: queue.Queue[DataPoint] = self._manager.Queue()
                # processed_data_points: queue.Queue[DataPoint] = self._manager.Queue()
                #
                # for data_point in range(no_data_points):
                #     data_points_to_process.put(data_point)
                #
                # src_dir = (
                #     str(
                #         ServiceConfig(
                #             config_sources=FileSource(
                #                 Path("config/experiment_library.yaml")
                #             )
                #         ).experiment_library_dir
                #     )
                #     if pre_processing_task.debug_mode
                #     else dir
                # )
                #
                # adapt the priority of the pre-processing worker according to the priority
                # of the task
                # change_process_priority(pre_processing_task.priority)
                #
                # prepare_experiment_library_folder(
                #     src_dir=src_dir, pre_processing_task=pre_processing_task
                # )
                # cache_local_params(pre_processing_task.timestamp)
                #
                # while processed_data_points.qsize() != no_data_points:
                #     # if not globals_are_up_to_date(globals_timestamp):
                #     #     globals_timestamp = cache_global_params()
                #
                #     try:
                #         data_point = pre_processing_task.get_next_data_point()
                #     except queue.Empty:
                #         time.sleep(0.001)
                #         continue
                #
                #     task = HardwareTask(
                #         pre_processing_task=pre_processing_task,
                #         data_point=data_point,
                #         globals_timestamp=time.time(),
                #         src_dir=src_dir,
                #     )
                #
                #     pre_processing_task.process_data_point(data_point)
                #
                #     logger.info(
                #         "(%s-%s) Submitting data point %s-%s.",
                #         worker_number,
                #         pre_processing_task.priority,
                #         pre_processing_task.name,
                #         data_point,
                #     )
                #     hardware_queue.put(task)
                # logger.info(
                #     "(%s-%s) Task '%s' finished",
                #     worker_number,
                #     pre_processing_task.priority,
                #     pre_processing_task.name,
                # )
