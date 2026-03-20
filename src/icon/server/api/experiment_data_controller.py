import asyncio
from dataclasses import asdict
from typing import Any

import numpy as np
import pydase

from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataRepository,
    delete_fit_result_by_job_id,
    write_fit_result_by_job_id,
)
from icon.server.fitting import run_curve_fit
from icon.server.web_server.socketio_emit_queue import emit_queue

__all__ = ["ExperimentDataController"]


class ExperimentDataController(pydase.DataService):
    """Controller for accessing stored experiment data.

    Provides API methods to fetch experiment data associated with jobs.
    """

    async def get_experiment_data_by_job_id(
        self, job_id: int, max_transfer_bytes: int = 50_000_000
    ) -> dict[str, Any]:
        """Return experiment data for a given job.

        Args:
            job_id: The unique identifier of the job.
            max_transfer_bytes: Approximate cap on the serialised payload
                size in bytes.  The number of data points loaded is
                derived from HDF5 metadata so that the response stays
                within this budget.  Defaults to 50 MB.

        Returns:
            The experiment data linked to the job as a dict resulting
            from serializing an
            [ExperimentData][icon.server.data_access.repositories.experiment_data_repository.ExperimentData]
            instance.
        """

        result = await asyncio.to_thread(
            ExperimentDataRepository.get_experiment_data_by_job_id,
            job_id=job_id,
            max_transfer_bytes=max_transfer_bytes,
        )
        return asdict(result)

    async def run_fit(
        self,
        job_id: int,
        result_channel: str,
        func_type: str,
        x_range: list[float] | None = None,
        init: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Run a curve fit on a result channel of a finished job.

        Args:
            job_id: Job identifier.
            result_channel: Name of the result channel to fit.
            func_type: Fit model name (e.g. "lorentzian").
            x_range: Optional [min, max] to restrict fit domain.
            init: Optional initial parameter overrides.

        Returns:
            Serialised FitResult dict.
        """
        data = await asyncio.to_thread(
            ExperimentDataRepository.get_experiment_data_by_job_id,
            job_id=job_id,
        )

        # Find the first non-timestamp scan parameter for x-values
        scan_param_name = next(
            (p for p in data.scan_parameters if p != "timestamp"), None
        )
        if scan_param_name is None:
            return asdict(run_curve_fit(
                x=np.array([]),
                y=np.array([]),
                result_channel=result_channel,
                func_type=func_type,  # type: ignore[arg-type]
            ))

        scan_values = data.scan_parameters[scan_param_name]
        channel_values = data.result_channels.get(result_channel, {})

        # Build aligned x, y arrays sorted by index
        indices = sorted(set(scan_values.keys()) & set(channel_values.keys()))
        x = np.array([float(scan_values[i]) for i in indices])
        y = np.array([float(channel_values[i]) for i in indices])

        fit_result = await asyncio.to_thread(
            run_curve_fit,
            x=x,
            y=y,
            result_channel=result_channel,
            func_type=func_type,  # type: ignore[arg-type]
            x_range=x_range,
            init=init,
        )

        if fit_result.success:
            await asyncio.to_thread(
                write_fit_result_by_job_id,
                job_id=job_id,
                fit_result=fit_result,
            )

        result_dict = asdict(fit_result)
        emit_queue.put({
            "event": f"experiment_fit_{job_id}",
            "data": result_dict,
        })
        return result_dict

    async def delete_fit(
        self,
        job_id: int,
        result_channel: str,
    ) -> None:
        """Delete a fit result for a result channel.

        Args:
            job_id: Job identifier.
            result_channel: Name of the result channel whose fit to remove.
        """
        await asyncio.to_thread(
            delete_fit_result_by_job_id,
            job_id=job_id,
            result_channel=result_channel,
        )
        emit_queue.put({
            "event": f"experiment_fit_{job_id}",
            "data": {"result_channel": result_channel, "deleted": True},
        })
