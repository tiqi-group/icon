from __future__ import annotations
import queue
import threading
import pytest
import asyncio
import multiprocessing

from datetime import datetime, UTC

from icon.server.data_access.repositories.experiment_source_repository import ExperimentSourceRepository
from icon.server.data_access.models.sqlite import ExperimentSource

from icon.server.scheduler.scheduler import Scheduler, initialise_job_tables

from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.data_access.repositories.job_transaction import JobTransaction
from icon.server.data_access.models.enums import JobStatus, JobRunStatus
from icon.server.data_access.models.sqlite.job import Job

from typing import TYPE_CHECKING, Any, Generator, AsyncGenerator, List, Callable, Sequence
if TYPE_CHECKING:
    from icon.server.pre_processing.task import PreProcessingTask
    from icon.server.data_access.models.sqlite.job_run import JobRun
    from pytest_mock import MockerFixture

DEFAULT_WAIT_FOR_JOB_HANDLED_TIMEOUT = 2  # seconds

class SchedulerTestFixture:
    def __init__(self) -> None:
        self.experiment_source = ExperimentSourceRepository.get_or_create_experiment(
            experiment_source=ExperimentSource(experiment_id="test_experiment_id")
        )
        self.ppq : queue.PriorityQueue[PreProcessingTask] = queue.PriorityQueue()
        self.scheduler = Scheduler(pre_processing_queue=self.ppq)
        self.thread = threading.Thread(target=self.scheduler.run, daemon=True)
        self.thread_running = False

    def start(self) -> None:
        self.thread.start()
        self.thread_running = True

    def stop(self) -> None:
        if self.thread_running == False:
            return
        self.scheduler.stop()
        self.thread.join()
        self.thread_running = False

    def insert_jobs(self, job_cnt:int=10, **kwargs:Any) -> List[Job]:
        jobs = []
        for _ in range(job_cnt):
            jobs.append(JobRepository.submit_job(job=Job(**dict(
                    experiment_source=self.experiment_source,
                    priority=20,
                    local_parameters_timestamp=datetime.now(tz=UTC),
                    scan_parameters=[],
                    repetitions=10,
                    git_commit_hash=None,
                    number_of_shots=50,
                    auto_calibration=False,
                    debug_mode=True
                ) | kwargs)))
        return jobs

    async def wait_for_jobs_handled(self, timeout:int = DEFAULT_WAIT_FOR_JOB_HANDLED_TIMEOUT) -> None:
        async def wait_task() -> None:
            while len(JobRepository.get_jobs_by_status_and_timeframe(
                    status=JobStatus.SUBMITTED
                )) > 0:
                await asyncio.sleep(0.1)
        try:
            await asyncio.wait_for(wait_task(), timeout=timeout)  # Wait until all jobs are handled
        except asyncio.TimeoutError:
            assert False, "Timeout reached while waiting for all submitted jobs to be handled by the scheduler."

    def assert_job_status(self, job_id:int, expected_job_status: JobStatus, expected_job_run_status: JobRunStatus|None = None) -> None:
        job = JobRepository.get_job_by_id(job_id=job_id)
        assert job.status == expected_job_status, f"Job {job.id} should be in {expected_job_status} status"
        if expected_job_run_status is not None:
            job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
            assert job_run.status == expected_job_run_status, f"JobRun for job {job.id} should be in {expected_job_run_status} status"

    async def _consume_ppq_check_priority(self, num_items_expected: int, timeout:int = DEFAULT_WAIT_FOR_JOB_HANDLED_TIMEOUT) -> AsyncGenerator[PreProcessingTask, None]:
        async def wait_task() -> None:
            while self.ppq.qsize() < num_items_expected:
                await asyncio.sleep(0.1)

        try:
            await asyncio.wait_for(wait_task(), timeout=timeout)  # Wait until all tasks are added to the pre-processing queue
        except asyncio.TimeoutError:
            assert False, "Scheduler did not add all tasks to the pre-processing queue within the expected time."

        try:
            last_priority = float('-inf')
            while not self.ppq.empty():
                pptask = self.ppq.get()
                assert pptask.priority >= last_priority, "Tasks retrieved from pre-processing queue are not in correct priority order."
                last_priority = pptask.priority
                yield pptask
            assert self.ppq.empty(), "Pre-processing queue should be empty after retrieving tasks."
        except queue.Empty:
            assert False, "Expecting more tasks in the pre-processing queue, but it was empty."


@pytest.fixture(scope="function")
def scheduler_fixture(request: pytest.FixtureRequest) -> Generator[SchedulerTestFixture, None, None]:
    start_thread = getattr(request, "param", True)
    fixture = SchedulerTestFixture()
    if start_thread:
        fixture.start()
    yield fixture
    fixture.stop()

@pytest.mark.asyncio
async def test_scheduler_process_jobs(scheduler_fixture: SchedulerTestFixture) -> None:
    """
        Create Jobs with varying priorities and let them be processed by the scheduler.
        Check database state and pre-processing queue order to ensure correct processing and priority handling.'''
    """

    NUM_JOBS = 10
    for k in range(NUM_JOBS):
        scheduler_fixture.insert_jobs(job_cnt=1, priority=10 + k*(2*(k%2)-1))

    async for pptask in scheduler_fixture._consume_ppq_check_priority(num_items_expected=NUM_JOBS):
        scheduler_fixture.assert_job_status(pptask.job.id, JobStatus.PROCESSING, JobRunStatus.PENDING)

@pytest.mark.asyncio
async def test_scheduler_queue_exception(mocker: MockerFixture, scheduler_fixture: SchedulerTestFixture) -> None:
    real_put = scheduler_fixture.ppq.put

    # Inject an Exception when scheduler tries to put to the pre-processing queue
    def failing_put() -> None:
        raise Exception("Intentional exception when adding task to pre-processing queue")
    mocker.patch.object(scheduler_fixture.ppq, "put", side_effect=failing_put)

    failed_jobs = scheduler_fixture.insert_jobs(job_cnt=10)
    await scheduler_fixture.wait_for_jobs_handled()

    for job_ in failed_jobs:
        # Failed Job should be in PROCESSED status with a CANCELLED JobRun
        scheduler_fixture.assert_job_status(job_.id, JobStatus.PROCESSED, JobRunStatus.FAILED)

    # Restore pre-processing queue
    mocker.patch.object(scheduler_fixture.ppq, "put", real_put)

    NUM_JOBS = 1
    scheduler_fixture.insert_jobs(job_cnt=NUM_JOBS)

    # The pre processing queue should contain the single new task
    async for pptask in scheduler_fixture._consume_ppq_check_priority(num_items_expected=NUM_JOBS):
        scheduler_fixture.assert_job_status(pptask.job.id, JobStatus.PROCESSING, JobRunStatus.PENDING)

    # No further jobs in SUBMITTED status expected
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.SUBMITTED)) == 0, "Expecting no jobs left in SUBMITTED status after processing."

@pytest.mark.asyncio
async def test_scheduler_db_exceptions(mocker: MockerFixture, scheduler_fixture: SchedulerTestFixture) -> None:
    real_get_jobs = JobRepository.get_jobs_by_status_and_timeframe
    real_insert_run = JobTransaction.insert_run_from_jobid

    # Inject an Exception on first 5 occurrences when scheduler tries to retrieve submitted jobs
    fail_get_jobs_cnt = multiprocessing.Value('i', 0)
    def failing_get_jobs(*args:Any, **kwargs:Any) -> Sequence[Job]:
        nonlocal fail_get_jobs_cnt
        fail_get_jobs_cnt.value += 1
        if fail_get_jobs_cnt.value <= 2:
            raise Exception("Intentional exception when fetching submitted jobs")
        else:
            return real_get_jobs(*args, **kwargs)

    mocker.patch.object(JobRepository, "get_jobs_by_status_and_timeframe", side_effect=failing_get_jobs)

    fail_insert_cnt = multiprocessing.Value('i', 0)
    def failing_insert_run(*args:Any, **kwargs:Any) -> tuple[Job, JobRun]:
        nonlocal fail_insert_cnt
        fail_insert_cnt.value += 1
        if fail_insert_cnt.value <= 5:
            raise Exception("Intentional exception when creating JobRun")
        else:
            return real_insert_run(*args, **kwargs)

    mocker.patch.object(JobTransaction, "insert_run_from_jobid", side_effect=failing_insert_run)


    NUM_JOBS = 10
    scheduler_fixture.insert_jobs(job_cnt=NUM_JOBS)

    async for pptask in scheduler_fixture._consume_ppq_check_priority(num_items_expected=NUM_JOBS, timeout=5):
        scheduler_fixture.assert_job_status(pptask.job.id, JobStatus.PROCESSING, JobRunStatus.PENDING)



@pytest.mark.asyncio
@pytest.mark.parametrize("scheduler_fixture", [False], indirect=True)
async def test_job_table_init(mocker: MockerFixture, scheduler_fixture: SchedulerTestFixture) -> None:
    assert scheduler_fixture.thread_running == False, "Scheduler thread should not be running for this test"
    ALL_JOBRUN_STATUSES = [v for v in JobRunStatus]

    initialise_job_tables()
    assert len(JobRepository.get_jobs_by_status_and_timeframe()) == 0, "Expecting no jobs to be present at startup"
    assert len(JobRunRepository.get_runs_by_status(status=ALL_JOBRUN_STATUSES)) == 0, "Expecting no job runs to be present at startup"

    NUM_JOBS = 10
    # Inserting jobs puts them in SUBMITTED status
    scheduler_fixture.insert_jobs(job_cnt=NUM_JOBS)
    initialise_job_tables()
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.SUBMITTED)) == NUM_JOBS, "Expecting all submitted jobs to remain in SUBMITTED status after initialization"

    # Process submitted jobs. Jobs should switch to PROCESSING.
    scheduler_fixture.scheduler._handle_submitted_jobs()
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.PROCESSING)) == NUM_JOBS, "Expecting all submitted jobs switch to PROCESSING status"
    assert len(JobRunRepository.get_runs_by_status(status=JobRunStatus.PENDING)) == NUM_JOBS, "JobRun with PENDING status should be created for each job"
    # All Proccessed Jobs should be switched to PROCESSED by the initialization
    initialise_job_tables()
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.PROCESSED)) == NUM_JOBS, "Expecting all submitted jobs switch to PROCESSING status"
    assert len(JobRepository.get_jobs_by_status_and_timeframe()) == NUM_JOBS, "Total job count should remain constant"
    assert len(JobRunRepository.get_runs_by_status(status=JobRunStatus.CANCELLED)) == NUM_JOBS, "Expecting all job runs to be marked as CANCELLED by initialization"
    assert len(JobRunRepository.get_runs_by_status(status=ALL_JOBRUN_STATUSES)) == NUM_JOBS, "Total job run count should remain constant"


