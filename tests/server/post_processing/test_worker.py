from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from icon.server.data_access.experiment_data import (
    ExperimentDataPoint,
    ExperimentDeviceDataPoint,
    HardwareProcessingError,
)
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.post_processing import worker as worker_module
from icon.server.post_processing.worker import PostProcessingWorker

if TYPE_CHECKING:
    from tests.server.conftest import SeedJob

HARDWARE_ERROR = "Sequence too long"


class _SingleTaskQueue:
    """Hands out one task, then stops the worker loop."""

    def __init__(self, task: Any) -> None:
        self._tasks = [task]

    def get(self) -> Any:
        if not self._tasks:
            # Caught by the worker's handle_keyboard_interrupt decorator.
            raise KeyboardInterrupt
        return self._tasks.pop()


def _run_worker(
    monkeypatch: pytest.MonkeyPatch, *, job_id: int, run_id: int, write: MagicMock
) -> None:
    monkeypatch.setattr(
        worker_module.ExperimentDataRepository, "write_experiment_data_by_job_id", write
    )
    task = SimpleNamespace(
        pre_processing_task=SimpleNamespace(
            job=SimpleNamespace(id=job_id), job_run=SimpleNamespace(id=run_id)
        ),
        data_point=ExperimentDataPoint(
            index=0,
            scan_params={},
            timestamp="2026-01-01T00:00:00",
            device_data=[
                ExperimentDeviceDataPoint(
                    device_id="zedboard",
                    readouts=HardwareProcessingError(message=HARDWARE_ERROR),
                    hardware_instructions="...",
                )
            ],
        ),
    )
    worker = PostProcessingWorker.__new__(PostProcessingWorker)
    worker._post_processing_queue = _SingleTaskQueue(task)  # type: ignore[assignment]
    worker.run()


@pytest.mark.parametrize("run_status", [JobRunStatus.FAILED, JobRunStatus.CANCELLED])
def test_tasks_of_stopped_jobs_are_written(
    monkeypatch: pytest.MonkeyPatch, seed_job: SeedJob, run_status: JobRunStatus
) -> None:
    job_id, run_id = seed_job(job_status=JobStatus.PROCESSED, run_status=run_status)
    write = MagicMock()

    _run_worker(monkeypatch, job_id=job_id, run_id=run_id, write=write)

    write.assert_called_once()
    assert write.call_args.kwargs["job_id"] == job_id


def test_write_error_keeps_log_of_failed_job(
    monkeypatch: pytest.MonkeyPatch, seed_job: SeedJob
) -> None:
    job_id, run_id = seed_job(
        job_status=JobStatus.PROCESSED, run_status=JobRunStatus.PROCESSING
    )
    JobRunRepository.update_run_by_id(
        run_id=run_id, status=JobRunStatus.FAILED, log=HARDWARE_ERROR
    )

    _run_worker(
        monkeypatch,
        job_id=job_id,
        run_id=run_id,
        write=MagicMock(side_effect=RuntimeError("disk full")),
    )

    job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
    assert job_run.status == JobRunStatus.FAILED
    assert job_run.log == HARDWARE_ERROR


@pytest.mark.parametrize("run_status", [JobRunStatus.PROCESSING, JobRunStatus.DONE])
def test_write_error_fails_active_or_done_job(
    monkeypatch: pytest.MonkeyPatch, seed_job: SeedJob, run_status: JobRunStatus
) -> None:
    job_id, run_id = seed_job(job_status=JobStatus.PROCESSED, run_status=run_status)

    _run_worker(
        monkeypatch,
        job_id=job_id,
        run_id=run_id,
        write=MagicMock(side_effect=RuntimeError("disk full")),
    )

    job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
    assert job_run.status == JobRunStatus.FAILED
    assert job_run.log == "Post-processing error: disk full"
