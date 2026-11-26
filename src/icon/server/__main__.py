from __future__ import annotations

import logging
import multiprocessing
import pathlib
from functools import partial
from importlib.metadata import distribution
from pathlib import Path
from typing import TYPE_CHECKING

import click
import pydase.server.web_server.api.v1.endpoints
import pydase.server.web_server.sio_setup
import pytz

import icon.serialization
import icon.server.shared_resource_manager
import icon.server.web_server.icon_server
from icon.config.config import Config
from icon.logging import setup_logging
from icon.server.api.api_service import APIService
from icon.server.data_access.db_context.sqlite.engine import CachedEngine
from icon.server.data_access.db_context.sqlite.migrations import run_migrations
from icon.server.data_access.reconfigurable_experiment_library_client import (
    ReconfigurableExperimentLibraryClient,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
from icon.server.hardware_processing.devices import Devices
from icon.server.hardware_processing.worker import (
    HardwareProcessingWorker,
)
from icon.server.post_processing.worker import PostProcessingWorker
from icon.server.pre_processing.worker import PreProcessingWorker
from icon.server.scheduler.scheduler import Scheduler
from icon.server.shared_resource_manager import SRM
from icon.server.web_server.sio_setup import patch_sio_setup
from icon.server.web_server.visualiser import patch_web_server

if TYPE_CHECKING:
    from icon.server.post_processing.task import PostProcessingTask
    from icon.server.utils.types import UpdateQueue
    from icon.server.web_server.socketio_emit_queue import EmitQueue


def patch_serialization_methods(timezone: pytz.BaseTzInfo) -> None:
    pydase.server.web_server.sio_setup.dump = partial(  # type: ignore[assignment]
        icon.serialization.dump, timezone=timezone
    )
    pydase.server.web_server.api.v1.endpoints.loads = icon.serialization.loads
    pydase.server.web_server.api.v1.endpoints.Serializer = (
        icon.serialization.IconSerializer.with_timezone(timezone)
    )


def _level_from_verbosity(v: int) -> int:
    level = logging.WARNING - 10 * v
    return min(max(level, logging.DEBUG), logging.CRITICAL)


def start_server(config: Config) -> None:
    patch_sio_setup()
    patch_web_server()
    patch_serialization_methods(pytz.timezone(config.get().date.timezone))
    engine_cache = CachedEngine(config.get().databases.sqlite.file)
    run_migrations(engine=engine_cache.get_cached(config.get().databases.sqlite.file))

    SRM.start_srm()

    # Created here, in the main process, before any worker is forked, so that
    # every consumer holds the queue the web server emits from.
    emit_queue: EmitQueue = multiprocessing.Queue()

    parameters_repository = ParametersRepository(
        shared_parameters=SRM.parameters_dict,
        influx_config=config.get().databases.influxdbv1,
        emit_queue=emit_queue,
    )

    children: list[multiprocessing.Process] = []

    scheduler = Scheduler(
        config,
        pre_processing_queue=SRM.pre_processing_queue,
        engine_cache=engine_cache,
        emit_queue=emit_queue,
    )
    scheduler.start()
    children.append(scheduler)

    number_of_pre_processing_workers = config.get().server.pre_processing.workers
    pre_processing_update_queues: list[multiprocessing.Queue[UpdateQueue]] = [
        multiprocessing.Queue() for _ in range(number_of_pre_processing_workers)
    ]
    exp_lib_client = ReconfigurableExperimentLibraryClient(config)
    devices = Devices(config)

    for i, queue in enumerate(pre_processing_update_queues):
        pre_processing_worker = PreProcessingWorker(
            config=config,
            experiment_library_client=exp_lib_client,
            worker_number=i,
            hardware_processing_queue=SRM.hardware_processing_queue,
            pre_processing_queue=SRM.pre_processing_queue,
            update_queue=queue,
            manager=SRM,
            engine_cache=engine_cache,
            parameters_repository=parameters_repository,
            emit_queue=emit_queue,
        )
        pre_processing_worker.start()
        children.append(pre_processing_worker)

    post_processing_queue: multiprocessing.Queue[PostProcessingTask] = (
        multiprocessing.Queue()
    )

    hardware_processing_worker = HardwareProcessingWorker(
        config=config,
        hardware_processing_queue=SRM.hardware_processing_queue,
        post_processing_queue=post_processing_queue,
        manager=SRM,
        devices=devices,
        engine_cache=engine_cache,
        emit_queue=emit_queue,
    )
    hardware_processing_worker.start()
    children.append(hardware_processing_worker)

    post_processing_worker = PostProcessingWorker(
        config=config,
        post_processing_queue=post_processing_queue,
        engine_cache=engine_cache,
        emit_queue=emit_queue,
    )
    post_processing_worker.start()
    children.append(post_processing_worker)

    try:
        icon.server.web_server.icon_server.IconServer(
            APIService(
                config=config,
                experiment_library_client=exp_lib_client,
                pre_processing_event_queues=pre_processing_update_queues,
                devices=devices,
                parameters_repository=parameters_repository,
                engine_cache=engine_cache,
                emit_queue=emit_queue,
            ),
            emit_queue=emit_queue,
            host=config.get().server.host,
            web_port=config.get().server.port,
            frontend_src=Path(__file__).parent / "frontend",
        ).run()
    finally:
        # Terminate the worker processes before shutting down the manager they
        # communicate with, so a stopping server never leaves stale workers
        # (notably the scheduler) polling the shared database.
        for child in children:
            child.terminate()
        for child in children:
            child.join(timeout=10)
        SRM.shutdown()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-V", "--version", is_flag=True, help="Print version.")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv).")
@click.option("-q", "--quiet", count=True, help="Decrease verbosity (-q).")
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=False, dir_okay=False, path_type=pathlib.Path),
    default=pathlib.Path.home() / ".config/icon/config.yaml",
    show_default=True,
    help="Path to the configuration file.",
)
def main(*, version: bool, verbose: int, quiet: int, config: pathlib.Path) -> None:
    """Start the ICON server."""
    if version:
        __version__ = distribution("icon").version
        click.echo(f"icon {__version__}")
        raise SystemExit(0)

    level = _level_from_verbosity(verbose - quiet)
    setup_logging(level)

    icon_config = Config(config)
    try:
        start_server(icon_config)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Exit")


if __name__ == "__main__":
    main()
