import logging
import os
from typing import Literal

import pandas as pd
from filelock import FileLock

from icon.server.data_access.repositories.job_run_repository import JobRunRepository

logger = logging.getLogger(__name__)


def get_filename_by_job_id(job_id: int) -> str:
    scheduled_time = JobRunRepository.get_scheduled_time_by_job_id(job_id=job_id)
    return f"{scheduled_time}.h5"


class ExperimentDataRepository:
    LOCK_EXTENSION = ".lock"
    KEY = "data"

    @staticmethod
    def write(
        *,
        job_id: int,
        data: pd.DataFrame,
        key: str = KEY,
        lock_extension: str = LOCK_EXTENSION,
    ) -> None:
        filename = get_filename_by_job_id(job_id)
        lock_path = "." + filename + lock_extension
        with FileLock(lock_path):
            mode: Literal["a", "w"] = "a" if os.path.exists(filename) else "w"

            data.to_hdf(filename, key=key, mode=mode, append=True, format="table")
            logger.debug("Appended data to %s", filename)

    @staticmethod
    def get_experiment_data_by_job_id(
        *,
        job_id: int,
        key: str = KEY,
        lock_extension: str = LOCK_EXTENSION,
    ) -> pd.DataFrame:
        filename = get_filename_by_job_id(job_id)
        lock_path = "." + filename + lock_extension
        with FileLock(lock_path):
            if not os.path.exists(filename):
                raise FileNotFoundError(f"The file {filename} does not exist.")
            return pd.read_hdf(filename, key=key)  # type: ignore [return-value]
