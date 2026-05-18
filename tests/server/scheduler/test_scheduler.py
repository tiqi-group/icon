import pytest
import time
import queue
import pathlib
import multiprocessing

from icon.config import get_config
from icon.server.data_access.repositories.experiment_source_repository import ExperimentSourceRepository
from icon.server.data_access.models.sqlite import ExperimentSource
from icon.server.pre_processing.task import PreProcessingTask

from icon.server.scheduler.scheduler import Scheduler

from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.models.sqlite.job import Job

import icon.server.shared_resource_manager

from datetime import datetime, UTC

# @pytest.fixture
# def mp_context():
#     return multiprocessing.get_context("spawn")

def test_scheduler():

    ppq = icon.server.shared_resource_manager.pre_processing_queue
    # ppq = multiprocessing.Queue()
    scheduler = Scheduler(ppq)
    # scheduler._popen = None
    # scheduler._start_method = mp_context.get_start_method()
    scheduler.start()

    experiment_source = ExperimentSource(experiment_id="test_experiment_id")

    experiment_source = ExperimentSourceRepository.get_or_create_experiment(
        experiment_source=experiment_source
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

    time.sleep(.5)

    try:
        for _ in range(NUM_TASKS):
            pptask = ppq.get(timeout=3)
            print(pptask)
        assert ppq.empty(), "Pre-processing queue should be empty after retrieving tasks."
    except queue.Empty:
        assert False, "No task found in pre-processing queue."
    finally:
        scheduler.stop()
        scheduler.join(timeout=1)

