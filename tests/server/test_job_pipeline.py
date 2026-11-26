"""End-to-end test of the job pipeline.

Runs the real scheduler, pre-processing, hardware-processing, and post-processing
workers as separate processes, coordinated through a real ``SharedResourceManager``,
against a real SQLite database and writing real HDF5 result files. Only the
experiment library (a trivial in-process client) and InfluxDB (a ``MagicMock``)
are mocked.
"""

import multiprocessing
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import h5py
import pytest
import pytz
import sqlalchemy.orm

from icon.server.data_access.db_context.sqlite.engine import CachedEngine
from icon.server.data_access.experiment_library_client import (
    ExperimentLibraryClient,
)
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite import Base, ExperimentSource, Job
from icon.server.data_access.reconfigurable_experiment_library_client import (
    ReconfigurableExperimentLibraryClient,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
)
from icon.server.hardware_processing.devices import Devices
from icon.server.hardware_processing.worker import HardwareProcessingWorker
from icon.server.post_processing.worker import PostProcessingWorker
from icon.server.pre_processing.worker import PreProcessingWorker
from icon.server.scheduler.scheduler import Scheduler
from icon.server.shared_resource_manager import SharedResourceManager
from tests.mock_config import mock_config

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from icon.config.config import Config
    from icon.server.api.models.experiment_dict import ExperimentDict
    from icon.server.data_access.experiment_data import (
        DatabaseValueType,
        ReadoutMetadata,
    )
    from icon.server.data_access.experiment_library_client import (
        ParameterMetadataDict,
    )
    from icon.server.post_processing.task import PostProcessingTask
    from icon.server.web_server.socketio_emit_queue import EmitQueue

EXPERIMENT_ID = "test_lib.SimpleExperiment (default)"
TIMEOUT_SECONDS = 60
"""How long to wait for the pipeline to finish the job before failing."""


class SimpleExperimentLibraryClient(ExperimentLibraryClient):
    """A trivial experiment library: one experiment, no parameters, no devices."""

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        return ({}, {"all parameters": {}, "display groups": {}})

    async def load_device_order(self) -> list[str]:
        return []

    async def create_hardware_instructions(
        self,
        *,
        exp_module_name: str,  # noqa: ARG002
        exp_instance_name: str,  # noqa: ARG002
        parameter_dict: "dict[str, DatabaseValueType]",  # noqa: ARG002
        n_shots: int,  # noqa: ARG002
    ) -> dict[str, str]:
        return {}

    async def get_experiment_readout_metadata(
        self,
        *,
        exp_module_name: str,  # noqa: ARG002
        exp_instance_name: str,  # noqa: ARG002
        parameter_dict: "dict[str, DatabaseValueType]",  # noqa: ARG002
    ) -> "list[tuple[str, ReadoutMetadata]]":
        return []

    async def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        return {}


@dataclass
class Pipeline:
    """A running job pipeline: scheduler plus all workers."""

    engine: "Engine"
    config: "Config"
    emit_queue: "EmitQueue"


@pytest.fixture
def pipeline(tmp_path: Path) -> Iterator[Pipeline]:
    """Start the scheduler and all workers as real processes on a temp database."""
    config = mock_config()
    h5_dir = tmp_path / "results"
    h5_dir.mkdir()
    config.get().databases.sqlite.file = str(tmp_path / "icon.db")
    config.get().data.results_dir = str(h5_dir)

    config.get().experiment_library.module = __name__
    config.get().experiment_library.client_class = "SimpleExperimentLibraryClient"

    engine_cache = CachedEngine(config.get().databases.sqlite.file)
    engine = engine_cache.get_cached(config.get().databases.sqlite.file)
    Base.metadata.create_all(engine)

    srm = SharedResourceManager()
    srm.start_srm()

    # Real queue, created in this process before the workers fork, exactly as in
    # start_server; the workers' puts must reach this same queue object.
    emit_queue: EmitQueue = multiprocessing.Queue()

    parameters_repository = MagicMock()
    parameters_repository.get_influxdb_parameters.return_value = {}

    scheduler = Scheduler(
        config,
        pre_processing_queue=srm.pre_processing_queue,
        engine_cache=engine_cache,
        emit_queue=emit_queue,
    )
    pre_processing_worker = PreProcessingWorker(
        config=config,
        worker_number=0,
        pre_processing_queue=srm.pre_processing_queue,
        update_queue=multiprocessing.Queue(),
        hardware_processing_queue=srm.hardware_processing_queue,
        manager=srm,
        experiment_library_client=ReconfigurableExperimentLibraryClient(config),
        engine_cache=engine_cache,
        parameters_repository=parameters_repository,
        emit_queue=emit_queue,
    )
    post_processing_queue: multiprocessing.Queue[PostProcessingTask] = (
        multiprocessing.Queue()
    )
    hardware_processing_worker = HardwareProcessingWorker(
        config=config,
        hardware_processing_queue=srm.hardware_processing_queue,
        post_processing_queue=post_processing_queue,
        manager=srm,
        devices=Devices(config),
        engine_cache=engine_cache,
        emit_queue=emit_queue,
    )
    post_processing_worker = PostProcessingWorker(
        config=config,
        post_processing_queue=post_processing_queue,
        engine_cache=engine_cache,
        emit_queue=emit_queue,
    )

    processes = [
        scheduler,
        pre_processing_worker,
        hardware_processing_worker,
        post_processing_worker,
    ]
    for process in processes:
        process.start()

    try:
        yield Pipeline(engine=engine, config=config, emit_queue=emit_queue)
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.join(timeout=10)
        srm.shutdown()


def _wait_for_processed(engine: "Engine", job_id: int) -> Job:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    job = JobRepository.get_job_by_id(engine=engine, job_id=job_id)
    while job.status != JobStatus.PROCESSED:
        if time.monotonic() > deadline:
            pytest.fail(
                f"Job {job_id} did not reach PROCESSED within "
                f"{TIMEOUT_SECONDS}s (status: {job.status})"
            )
        time.sleep(0.2)
        job = JobRepository.get_job_by_id(engine=engine, job_id=job_id)
    return job


def test_job_runs_through_the_whole_pipeline(pipeline: Pipeline) -> None:
    engine, config = pipeline.engine, pipeline.config

    with sqlalchemy.orm.Session(engine) as session:
        source = ExperimentSource(experiment_id=EXPERIMENT_ID)
        session.add(source)
        session.commit()
        source_id = source.id

    job = Job(experiment_source_id=source_id)
    JobRepository(
        pytz.timezone(config.get().date.timezone), engine, pipeline.emit_queue
    ).submit_job(job=job)

    _wait_for_processed(engine, job.id)

    run = JobRunRepository.get_run_by_job_id(engine=engine, job_id=job.id)
    assert run.status is JobRunStatus.DONE

    result_files = list(Path(config.get().data.results_dir).glob("*.h5"))
    assert len(result_files) == 1
    with h5py.File(result_files[0], "r") as h5file:
        assert h5file.attrs["experiment_id"] == EXPERIMENT_ID
        assert int(h5file.attrs["job_id"]) == job.id
        assert int(h5file.attrs["number_of_data_points"]) == 1
