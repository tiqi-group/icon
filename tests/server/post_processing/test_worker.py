from __future__ import annotations

import copy
from contextlib import contextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest

from icon.server.data_access.experiment_data import (
    DatabaseValueType,
    ExperimentDataPoint,
    ExperimentDeviceDataPoint,
    HardwareProcessingError,
    Readouts,
)
from icon.server.data_access.experiment_library_client import ExperimentLibraryClient
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.post_processing import worker as worker_module
from icon.server.post_processing.worker import PostProcessingWorker

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.server.conftest import SeedJob

HARDWARE_ERROR = "Sequence too long"
EXPERIMENT_ID = "experiment_library.experiments.detection.Detection (Det)"
PARAMETER_DICT: dict[str, DatabaseValueType] = {"threshold": 2}


class _TaskQueue:
    """Hands out the tasks in order, then stops the worker loop."""

    def __init__(self, tasks: list[Any]) -> None:
        self._tasks = list(tasks)

    def get(self, timeout: float | None = None) -> Any:  # noqa: ARG002
        if not self._tasks:
            # Caught by the worker's handle_keyboard_interrupt decorator.
            raise KeyboardInterrupt
        return self._tasks.pop(0)


class _FakeClient(ExperimentLibraryClient):
    """Runs `post_processing` on a copy of the data point, like the venv does."""

    def __init__(
        self,
        post_processing: Callable[[ExperimentDataPoint], ExperimentDataPoint | None],
    ) -> None:
        self._post_processing = post_processing
        self.calls: list[dict[str, Any]] = []
        self.reused = 0

    @contextmanager
    def reuse_venv(self) -> Iterator[None]:
        self.reused += 1
        yield

    async def post_process(self, **kwargs: Any) -> ExperimentDataPoint | None:
        self.calls.append(kwargs)
        return self._post_processing(copy.deepcopy(kwargs["data_point"]))


def _unchanged(data_point: ExperimentDataPoint) -> ExperimentDataPoint:
    return data_point


def _readouts(data_point: ExperimentDataPoint) -> Readouts:
    return cast("Readouts", data_point.device_data[0].readouts)


def _data_point(index: int = 0, *, failed: bool = False) -> ExperimentDataPoint:
    return ExperimentDataPoint(
        index=index,
        scan_params={},
        timestamp="2026-01-01T00:00:00",
        device_data=[
            ExperimentDeviceDataPoint(
                device_id="zedboard",
                readouts=HardwareProcessingError(message=HARDWARE_ERROR)
                if failed
                else Readouts(
                    result_channels={"raw": 1.0},
                    vector_channels={},
                    shot_channels={"counts": [1, 3]},
                ),
                hardware_instructions="...",
            )
        ],
    )


def _task(job_id: int, run_id: int, data_point: ExperimentDataPoint) -> Any:
    return SimpleNamespace(
        pre_processing_task=SimpleNamespace(
            job=SimpleNamespace(
                id=job_id,
                experiment_source=SimpleNamespace(experiment_id=EXPERIMENT_ID),
            ),
            job_run=SimpleNamespace(id=run_id),
        ),
        data_point=data_point,
        parameter_dict=PARAMETER_DICT,
    )


def _run_worker(
    monkeypatch: pytest.MonkeyPatch,
    tasks: list[Any],
    *,
    write: MagicMock,
    client: ExperimentLibraryClient | None = None,
) -> None:
    monkeypatch.setattr(
        worker_module.ExperimentDataRepository, "write_experiment_data_by_job_id", write
    )
    worker = PostProcessingWorker(
        post_processing_queue=cast("Any", _TaskQueue(tasks)),
        experiment_library_client=client or _FakeClient(_unchanged),
    )
    worker.run()


def _written(write: MagicMock) -> list[ExperimentDataPoint]:
    return [call.kwargs["data_point"] for call in write.call_args_list]


@pytest.mark.parametrize("run_status", [JobRunStatus.FAILED, JobRunStatus.CANCELLED])
def test_tasks_of_stopped_jobs_are_written(
    monkeypatch: pytest.MonkeyPatch, seed_job: SeedJob, run_status: JobRunStatus
) -> None:
    job_id, run_id = seed_job(job_status=JobStatus.PROCESSED, run_status=run_status)
    write = MagicMock()
    client = _FakeClient(_unchanged)

    _run_worker(
        monkeypatch,
        [_task(job_id, run_id, _data_point(failed=True))],
        write=write,
        client=client,
    )

    write.assert_called_once()
    assert write.call_args.kwargs["job_id"] == job_id
    # Data points that failed on a device are not post-processed
    assert client.calls == []


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
        [_task(job_id, run_id, _data_point(failed=True))],
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
        [_task(job_id, run_id, _data_point(failed=True))],
        write=MagicMock(side_effect=RuntimeError("disk full")),
    )

    job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
    assert job_run.status == JobRunStatus.FAILED
    assert job_run.log == "Post-processing error: disk full"


def test_derived_channels_are_added_and_raw_channels_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def post_processing(data_point: ExperimentDataPoint) -> ExperimentDataPoint:
        readouts = _readouts(data_point)
        readouts.result_channels["derived"] = 2.0
        # Raw channels are read-only: these changes are ignored
        readouts.result_channels["raw"] = 99.0
        readouts.shot_channels["counts"] = []
        return data_point

    write = MagicMock()
    client = _FakeClient(post_processing)

    _run_worker(monkeypatch, [_task(1, 1, _data_point())], write=write, client=client)

    [written] = _written(write)
    assert _readouts(written).result_channels == {"raw": 1.0, "derived": 2.0}
    assert _readouts(written).shot_channels == {"counts": [1, 3]}
    [call] = client.calls
    assert call["exp_module_name"] == "experiment_library.experiments.detection"
    assert call["exp_instance_name"] == "Det"
    assert call["parameter_dict"] == PARAMETER_DICT


def test_post_processing_error_keeps_raw_data_and_logs_to_the_run(
    monkeypatch: pytest.MonkeyPatch, seed_job: SeedJob
) -> None:
    job_id, run_id = seed_job(
        job_status=JobStatus.PROCESSING, run_status=JobRunStatus.PROCESSING
    )

    def post_processing(data_point: ExperimentDataPoint) -> ExperimentDataPoint:
        raise ZeroDivisionError(f"division by zero in {data_point.index}")

    write = MagicMock()
    tasks = [_task(job_id, run_id, _data_point(index)) for index in range(2)]

    _run_worker(monkeypatch, tasks, write=write, client=_FakeClient(post_processing))

    # The data points are written as read out, so the derived channels are NaN
    assert _written(write) == [task.data_point for task in tasks]
    job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
    assert job_run.status == JobRunStatus.PROCESSING
    # Only the first error is logged
    assert job_run.log is not None
    assert job_run.log.startswith(
        "Post-processing of data point 0: division by zero in 0"
    )

    # Updating the status keeps the log
    JobRunRepository.update_run_by_id(run_id=run_id, status=JobRunStatus.DONE)
    assert JobRunRepository.get_run_by_job_id(job_id=job_id).log == job_run.log


def test_experiment_without_post_processing_is_called_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write = MagicMock()
    client = _FakeClient(lambda _: None)
    tasks = [
        _task(1, 1, _data_point(0)),
        _task(1, 1, _data_point(1)),
        _task(2, 2, _data_point(0)),
    ]

    _run_worker(monkeypatch, tasks, write=write, client=client)

    assert _written(write) == [task.data_point for task in tasks]
    # Once for each of the two job runs
    n_runs = len({task.pre_processing_task.job_run.id for task in tasks})
    assert len(client.calls) == n_runs
    assert client.reused == n_runs
