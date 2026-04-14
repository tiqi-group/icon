"""Auto-fit: repeat the previous fit when a new job finishes."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

import numpy as np

from icon.server.data_access.models.enums import JobStatus
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentData,
    ExperimentDataRepository,
    get_fit_results_by_job_id,
    write_fit_result_by_job_id,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.fitting.fit_runner import run_curve_fit
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


def try_auto_fit(job_id: int, experiment_source_id: int) -> None:
    """Auto-fit the new job using the fit config from the previous job.

    Looks up the most recent previous PROCESSED job for the same experiment
    source that has a stored fit, then runs the same model on the new data
    with fresh initial guesses.  Failures are logged but never raised.

    Args:
        job_id: The newly completed job.
        experiment_source_id: The experiment source to find previous jobs.
    """
    try:
        _auto_fit(job_id, experiment_source_id)
    except Exception:
        logger.exception("Auto-fit failed for job %d", job_id)


def _auto_fit(job_id: int, experiment_source_id: int) -> None:
    previous_job_id = _find_previous_job_with_fit(
        experiment_source_id, exclude_job_id=job_id
    )
    if previous_job_id is None:
        return

    previous_fits = get_fit_results_by_job_id(job_id=previous_job_id)
    if not previous_fits:
        return

    data = ExperimentDataRepository.get_experiment_data_by_job_id(
        job_id=job_id,
        max_transfer_bytes=2**62,
    )

    scan_param_name = next(
        (p for p in data.scan_parameters if p != "timestamp"), None
    )
    if scan_param_name is None:
        return

    for channel_name, fit_data in previous_fits.items():
        if fit_data.get("success") and fit_data.get("func_type"):
            _fit_channel(job_id, data, scan_param_name, channel_name, fit_data)


def _fit_channel(
    job_id: int,
    data: ExperimentData,
    scan_param_name: str,
    channel_name: str,
    fit_data: dict[str, Any],
) -> None:
    """Run a single auto-fit for one channel and persist the result."""
    channel_values = data.result_channels.get(channel_name, {})
    if not channel_values:
        return

    scan_values = data.scan_parameters[scan_param_name]
    indices = sorted(
        set(scan_values.keys()) & set(channel_values.keys())
    )
    x = np.array([float(scan_values[i]) for i in indices])
    y = np.array([float(channel_values[i]) for i in indices])

    func_type = fit_data["func_type"]
    fit_result = run_curve_fit(
        x=x,
        y=y,
        result_channel=channel_name,
        func_type=func_type,  # type: ignore[arg-type]
    )

    if fit_result.success:
        write_fit_result_by_job_id(job_id=job_id, fit_result=fit_result)
        emit_queue.put({
            "event": f"experiment_fit_{job_id}",
            "data": asdict(fit_result),
        })
        logger.info(
            "Auto-fit %s on job %d channel '%s' succeeded",
            func_type,
            job_id,
            channel_name,
        )
    else:
        logger.warning(
            "Auto-fit %s on job %d channel '%s' failed: %s",
            func_type,
            job_id,
            channel_name,
            fit_result.message,
        )


_MAX_PREVIOUS_JOBS_TO_CHECK = 10


def _find_previous_job_with_fit(
    experiment_source_id: int,
    exclude_job_id: int,
) -> int | None:
    """Find the most recent PROCESSED job with a stored fit.

    Only checks the last few jobs to avoid scanning the entire history.
    """
    rows = JobRepository.get_job_by_experiment_source_and_status(
        experiment_source_id=experiment_source_id,
        status=JobStatus.PROCESSED,
    )
    # Rows are ordered by (priority asc, created asc), so iterate in reverse
    checked = 0
    for (job,) in reversed(rows):
        if job.id == exclude_job_id:
            continue
        fits = get_fit_results_by_job_id(job_id=job.id)
        if fits:
            return job.id
        checked += 1
        if checked >= _MAX_PREVIOUS_JOBS_TO_CHECK:
            break
    return None
