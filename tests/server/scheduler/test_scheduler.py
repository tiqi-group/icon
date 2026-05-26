from typing import Generator, AsyncGenerator
import queue
import threading
import pytest
import asyncio

from icon.server.data_access.repositories.experiment_source_repository import ExperimentSourceRepository
from icon.server.data_access.models.sqlite import ExperimentSource
from icon.server.pre_processing.task import PreProcessingTask

from icon.server.scheduler.scheduler import Scheduler

from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.data_access.models.enums import JobStatus

from icon.server.data_access.models.sqlite.job import Job

from datetime import datetime, UTC

async def _consume_ppq_check_priority(ppq: queue.PriorityQueue[PreProcessingTask], num_items_expected: int) -> AsyncGenerator[PreProcessingTask, None]:
    async def wait_for_tasks() -> None:
        while ppq.qsize() < num_items_expected:
            await asyncio.sleep(0.1)

    try:
        await asyncio.wait_for(wait_for_tasks(), timeout=2)  # Wait until all tasks are added to the pre-processing queue
    except asyncio.TimeoutError:
        assert False, "Scheduler did not add all tasks to the pre-processing queue within the expected time."

    try:
        last_priority = float('-inf')
        while not ppq.empty():
            pptask = ppq.get()
            assert pptask.priority >= last_priority, "Tasks retrieved from pre-processing queue are not in correct priority order."
            last_priority = pptask.priority
            yield pptask
        assert ppq.empty(), "Pre-processing queue should be empty after retrieving tasks."
    except queue.Empty:
        assert False, "Expecting more tasks in the pre-processing queue, but it was empty."


@pytest.fixture()
def scheduler_fixture() -> Generator[queue.PriorityQueue[PreProcessingTask], None, None]:
    ppq: queue.PriorityQueue[PreProcessingTask] = queue.PriorityQueue()  # Use a local PriorityQueue for testing without multiprocessing complexities
    scheduler = Scheduler(ppq)

    # run scheduler.run in a thread to allow it to process the queue while we check the results
    thread = threading.Thread(target=scheduler.run, daemon=True)
    thread.start()

    yield ppq

    scheduler.stop()
    thread.join()


@pytest.mark.asyncio
async def test_scheduler(scheduler_fixture: queue.PriorityQueue[PreProcessingTask]) -> None:
    experiment_source = ExperimentSourceRepository.get_or_create_experiment(
        experiment_source=ExperimentSource(experiment_id="test_experiment_id")
    )

    NUM_TASKS = 10
    for k in range(NUM_TASKS):
        JobRepository.submit_job(job=Job(
            experiment_source=experiment_source,
            priority=10 + k*(2*(k%2)-1),
            local_parameters_timestamp=datetime.now(tz=UTC),
            scan_parameters=[],
            repetitions=10,
            git_commit_hash=None,
            number_of_shots=50,
            auto_calibration=False,
            debug_mode=True,
        ))

    ppq = scheduler_fixture

    async for pptask in _consume_ppq_check_priority(ppq, num_items_expected=NUM_TASKS):
        job = JobRepository.get_job_by_id(job_id=pptask.job.id)  # Check that the job still exists in the repository
        assert job.status == JobStatus.PROCESSING, f"Job {job.id} should be in PROCESSING status after being picked up by the scheduler."
        # job_run = JobRunRepository.get_run_by_job_id(job_id=pptask.job.id)
        # assert pptask.job == job, "The job in the pre-processing task should match the job retrieved from the repository."
        # print(job)
        # print(job_run)
        # print(pptask)
