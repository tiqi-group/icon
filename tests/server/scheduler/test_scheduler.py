from __future__ import annotations

import asyncio
import queue
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite import ExperimentSource
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.repositories.experiment_source_repository import (
    ExperimentSourceRepository,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.data_access.repositories.job_transaction import JobTransaction
from icon.server.scheduler.scheduler import Scheduler, initialise_job_tables

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from pytest_mock import MockerFixture

    from icon.server.pre_processing.task import PreProcessingTask

DEFAULT_WAIT_FOR_JOB_HANDLED_TIMEOUT = 2  # seconds
TEST_EXPERIMENT_ID = "test_experiment_id"

class IntentionalError(Exception):
    """Custom exception class for intentional errors for testing purposes."""

class SchedulerTestFixture:

    def __init__(self) -> None:
        self.experiment_source = ExperimentSourceRepository.get_or_create_experiment(
            experiment_source=ExperimentSource(experiment_id=TEST_EXPERIMENT_ID)
        )
        self.ppq : queue.PriorityQueue[PreProcessingTask] = queue.PriorityQueue()
        self.scheduler = Scheduler(pre_processing_queue=self.ppq)
        self.thread = threading.Thread(target=self.scheduler.run, daemon=True)
        self.thread_running = False

    def start(self) -> None:
        self.thread.start()
        self.thread_running = True

    def stop(self) -> None:
        if not self.thread_running:
            return
        self.scheduler.stop()
        self.thread.join()
        self.thread_running = False

    def insert_jobs(self, job_cnt:int=10, **kwargs:Any) -> list[Job]:
        return [ JobRepository.submit_job(job=Job(**dict(  # noqa: C408
                    experiment_source=self.experiment_source,
                    priority=20,
                    local_parameters_timestamp=datetime.now(tz=UTC),
                    scan_parameters=[],
                    repetitions=10,
                    git_commit_hash=None,
                    number_of_shots=50,
                    auto_calibration=False,
                    debug_mode=True
                ) | kwargs))
            for _ in range(job_cnt) ]

    async def wait_for_jobs_handled(self, timeout:int = DEFAULT_WAIT_FOR_JOB_HANDLED_TIMEOUT) -> None:
        async def wait_task() -> None:
            while len(JobRepository.get_jobs_by_status_and_timeframe(  # noqa: ASYNC110
                    status=JobStatus.SUBMITTED
                )) > 0:
                await asyncio.sleep(0.1)
        try:
            await asyncio.wait_for(wait_task(), timeout=timeout)  # Wait until all jobs are handled
        except asyncio.TimeoutError:
            pytest.fail("Timeout reached while waiting for all submitted jobs to be handled by the scheduler.")

    def assert_job_status(self, job_id:int, expected_job_status: JobStatus, expected_job_run_status: JobRunStatus|None = None) -> None:
        job = JobRepository.get_job_by_id(job_id=job_id)
        assert job.status == expected_job_status, f"Job {job.id} should be in {expected_job_status} status"
        if expected_job_run_status is not None:
            job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
            assert job_run.status == expected_job_run_status, f"JobRun for job {job.id} should be in {expected_job_run_status} status"

    async def _consume_ppq_check_priority(self, num_items_expected: int, timeout:int = DEFAULT_WAIT_FOR_JOB_HANDLED_TIMEOUT) -> AsyncGenerator[PreProcessingTask, None]:
        async def wait_task() -> None:
            while self.ppq.qsize() < num_items_expected:  # noqa: ASYNC110
                await asyncio.sleep(0.1)

        try:
            await asyncio.wait_for(wait_task(), timeout=timeout)  # Wait until all tasks are added to the pre-processing queue
        except asyncio.TimeoutError:
            pytest.fail("Timeout reached while waiting for all tasks to be added to the pre-processing queue.")

        last_priority = float("-inf")
        while not self.ppq.empty():
            pptask = self.ppq.get()
            assert pptask.priority >= last_priority, "Tasks retrieved from pre-processing queue are not in correct priority order."
            last_priority = pptask.priority
            yield pptask


@pytest.fixture # default scope: function
def scheduler_fixture(request: pytest.FixtureRequest) -> Generator[SchedulerTestFixture, None, None]:
    start_thread = getattr(request, "param", True)
    fixture = SchedulerTestFixture()
    if start_thread:
        fixture.start()
    yield fixture
    fixture.stop()

@pytest.mark.asyncio
async def test_scheduler_process_jobs(scheduler_fixture: SchedulerTestFixture) -> None:
    """Create Jobs with varying priorities and let them be processed by the scheduler and check database state and pre-processing queue order to ensure consistency."""
    _num_jobs = 10
    for k in range(_num_jobs):
        scheduler_fixture.insert_jobs(job_cnt=1, priority=10+k*(2*(k%2)-1)) # Insert jobs with alternating higher and lower priorities

    async for pptask in scheduler_fixture._consume_ppq_check_priority(num_items_expected=_num_jobs):
        scheduler_fixture.assert_job_status(pptask.job.id, JobStatus.PROCESSING, JobRunStatus.PENDING)
        assert pptask.job.experiment_source.experiment_id == TEST_EXPERIMENT_ID, "Experiment source ID should match"
        assert len(pptask.job.scan_parameters) == 0, "Scan parameters list expted to be empty"

@pytest.mark.asyncio
async def test_scheduler_queue_exception(mocker: MockerFixture, scheduler_fixture: SchedulerTestFixture) -> None:
    """Test the exception handling when inserting into the pre-processing queue. Jobs are expected to be marked as PROCESSED and their corresponding JobRuns as FAILED."""
    real_put = scheduler_fixture.ppq.put

    # Inject an Exception when scheduler tries to put to the pre-processing queue
    def failing_put() -> None:
        raise IntentionalError("Intentional exception when adding task to pre-processing queue")
    mocker.patch.object(scheduler_fixture.ppq, "put", side_effect=failing_put)

    failed_jobs = scheduler_fixture.insert_jobs(job_cnt=10)
    await scheduler_fixture.wait_for_jobs_handled()

    for job_ in failed_jobs:
        # Failed Job should be in PROCESSED status with a CANCELLED JobRun
        scheduler_fixture.assert_job_status(job_.id, JobStatus.PROCESSED, JobRunStatus.FAILED)

    # Restore pre-processing queue
    mocker.patch.object(scheduler_fixture.ppq, "put", real_put)

    _num_jobs = 1
    scheduler_fixture.insert_jobs(job_cnt=_num_jobs)

    # The pre processing queue should contain the single new task
    async for pptask in scheduler_fixture._consume_ppq_check_priority(num_items_expected=_num_jobs):
        scheduler_fixture.assert_job_status(pptask.job.id, JobStatus.PROCESSING, JobRunStatus.PENDING)

    # No further jobs in SUBMITTED status expected
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.SUBMITTED)) == 0, "Expecting no jobs left in SUBMITTED status after processing."

@pytest.mark.asyncio
@pytest.mark.parametrize("scheduler_fixture", [False], indirect=True) # Don't start the scheduler thread
async def test_scheduler_db_exceptions(mocker: MockerFixture, scheduler_fixture: SchedulerTestFixture) -> None:
    assert not scheduler_fixture.thread_running, "Scheduler thread should not be running for this test"

    _num_jobs = 10
    scheduler_fixture.insert_jobs(job_cnt=_num_jobs)
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.SUBMITTED)) == _num_jobs, "Expecting all inserted jobs to be in SUBMITTED status before processing"

    for patch_class, patch_method in [
        (JobRepository, "get_jobs_by_status_and_timeframe"),
        (JobTransaction, "insert_run_from_jobid")
    ]:
        # Inject an Exception when scheduler tries to fetch submitted jobs
        m = mocker.patch.object(patch_class, patch_method, side_effect=IntentionalError(f"Intentional exception on {patch_method}.{patch_method}"))
        scheduler_fixture.scheduler._handle_submitted_jobs()
        m.assert_called()
        mocker.stopall()
        assert scheduler_fixture.ppq.empty(), "Pre-processing queue should be empty when database fetch fails"
        assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.SUBMITTED)) == _num_jobs, "Expecting all jobs to remain in SUBMITTED status when database fetch fails"

    # With exceptions resolved, scheduler should be able to process jobs and add tasks to the pre-processing queue
    scheduler_fixture.scheduler._handle_submitted_jobs()

    async for pptask in scheduler_fixture._consume_ppq_check_priority(num_items_expected=_num_jobs, timeout=2):
        scheduler_fixture.assert_job_status(pptask.job.id, JobStatus.PROCESSING, JobRunStatus.PENDING)


@pytest.mark.asyncio
@pytest.mark.parametrize("scheduler_fixture", [False], indirect=True)  # Don't start the scheduler thread
async def test_job_table_init(scheduler_fixture: SchedulerTestFixture) -> None:
    assert not scheduler_fixture.thread_running, "Scheduler thread should not be running for this test"

    initialise_job_tables()
    assert len(JobRepository.get_jobs_by_status_and_timeframe()) == 0, "Expecting no jobs to be present at startup"
    assert len(JobRunRepository.get_runs_by_status(status=list(JobRunStatus))) == 0, "Expecting no job runs to be present at startup"

    _num_jobs = 10
    # Inserting jobs puts them in SUBMITTED status
    scheduler_fixture.insert_jobs(job_cnt=_num_jobs)
    initialise_job_tables()
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.SUBMITTED)) == _num_jobs, "Expecting all submitted jobs to remain in SUBMITTED status after initialization"

    # Process submitted jobs. Jobs should switch to PROCESSING.
    scheduler_fixture.scheduler._handle_submitted_jobs()
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.PROCESSING)) == _num_jobs, "Expecting all submitted jobs switch to PROCESSING status"
    assert len(JobRunRepository.get_runs_by_status(status=JobRunStatus.PENDING)) == _num_jobs, "JobRun with PENDING status should be created for each job"
    # All Proccessed Jobs should be switched to PROCESSED by the initialization
    initialise_job_tables()
    assert len(JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.PROCESSED)) == _num_jobs, "Expecting all submitted jobs switch to PROCESSING status"
    assert len(JobRepository.get_jobs_by_status_and_timeframe()) == _num_jobs, "Total job count should remain constant"
    assert len(JobRunRepository.get_runs_by_status(status=JobRunStatus.CANCELLED)) == _num_jobs, "Expecting all job runs to be marked as CANCELLED by initialization"
    assert len(JobRunRepository.get_runs_by_status(status=list(JobRunStatus))) == _num_jobs, "Total job run count should remain constant"
