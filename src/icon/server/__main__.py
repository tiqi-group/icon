# ruff: noqa: PLC0415
from __future__ import annotations

import logging
import pathlib
from functools import partial
from typing import TYPE_CHECKING

import click
import pytz

from icon.config.config import Config
from icon.logging import setup_logging
from icon.server.data_access.reconfigurable_experiment_library_client import (
    ReconfigurableExperimentLibraryClient,
)
from icon.server.hardware_processing.devices import Devices
from icon.server.shared_resource_manager import SRM

if TYPE_CHECKING:
    from icon.server.post_processing.task import PostProcessingTask


def patch_serialization_methods(timezone: pytz.BaseTzInfo) -> None:
    import pydase.server.web_server.api.v1.endpoints
    import pydase.server.web_server.sio_setup

    import icon.serialization

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
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from icon.server.utils.types import UpdateQueue
    import multiprocessing
    from pathlib import Path

    import icon.server.shared_resource_manager
    import icon.server.web_server.icon_server
    from icon.server.api.api_service import APIService
    from icon.server.data_access.db_context.sqlite.engine import initialize_engine
    from icon.server.data_access.db_context.sqlite.migrations import run_migrations
    from icon.server.hardware_processing.worker import (
        HardwareProcessingWorker,
    )
    from icon.server.post_processing.worker import PostProcessingWorker
    from icon.server.pre_processing.worker import PreProcessingWorker
    from icon.server.scheduler.scheduler import Scheduler
    from icon.server.web_server.sio_setup import patch_sio_setup
    from icon.server.web_server.visualiser import patch_web_server

    patch_sio_setup()
    patch_web_server()
    patch_serialization_methods(pytz.timezone(config.get().date.timezone))
    initialize_engine(config)
    run_migrations()

    SRM.start_srm()

    scheduler = Scheduler(config, pre_processing_queue=SRM.pre_processing_queue)
    scheduler.start()

    number_of_pre_processing_workers = config.get().server.pre_processing.workers
    pre_processing_update_queues: list[multiprocessing.Queue[UpdateQueue]] = [
        multiprocessing.Queue() for _ in range(number_of_pre_processing_workers)
    ]
    exp_lib_client = ReconfigurableExperimentLibraryClient(config)
    devices = Devices(config)

    for i, queue in enumerate(pre_processing_update_queues):
        PreProcessingWorker(
            config=config,
            experiment_library_client=exp_lib_client,
            worker_number=i,
            hardware_processing_queue=SRM.hardware_processing_queue,
            pre_processing_queue=SRM.pre_processing_queue,
            update_queue=queue,
            manager=SRM,
        ).start()

    post_processing_queue: multiprocessing.Queue[PostProcessingTask] = (
        multiprocessing.Queue()
    )

    hardware_processing_worker = HardwareProcessingWorker(
        config=config,
        hardware_processing_queue=SRM.hardware_processing_queue,
        post_processing_queue=post_processing_queue,
        manager=SRM,
        devices=devices,
    )
    hardware_processing_worker.start()

    post_processing_worker = PostProcessingWorker(
        config=config, post_processing_queue=post_processing_queue
    )
    post_processing_worker.start()

    icon.server.web_server.icon_server.IconServer(
        APIService(
            config=config,
            experiment_library_client=exp_lib_client,
            pre_processing_event_queues=pre_processing_update_queues,
            devices=devices,
        ),
        host=config.get().server.host,
        web_port=config.get().server.port,
        frontend_src=Path(__file__).parent / "frontend",
    ).run()


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
        from importlib.metadata import distribution

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
