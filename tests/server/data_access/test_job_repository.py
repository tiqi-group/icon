from __future__ import annotations

from typing import TYPE_CHECKING

from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository

if TYPE_CHECKING:
    from tests.server.conftest import SeedJob


def test_job_list_has_log_of_failed_run(seed_job: SeedJob) -> None:
    job_id, run_id = seed_job(
        job_status=JobStatus.PROCESSING, run_status=JobRunStatus.PROCESSING
    )
    (item,) = JobRepository.get_job_list()
    assert item["run_log"] is None

    JobRunRepository.update_run_by_id(
        run_id=run_id,
        status=JobRunStatus.FAILED,
        log="rfsoc: no response to exp.StartTask within 5s",
    )

    (item,) = JobRepository.get_job_list()
    assert item["id"] == job_id
    assert item["run_status"] == JobRunStatus.FAILED.value
    assert item["run_log"] == "rfsoc: no response to exp.StartTask within 5s"
