# ruff: noqa: PLC0415
from __future__ import annotations

import logging
import pathlib

import click

from icon.config.config_path import set_config_path
from icon.logging import setup_logging


def patch_serialization_methods() -> None:
    import pydase.server.web_server.api.v1.endpoints
    import pydase.server.web_server.sio_setup

    import icon.serialization

    pydase.server.web_server.sio_setup.dump = icon.serialization.dump  # type: ignore
    pydase.server.web_server.api.v1.endpoints.loads = icon.serialization.loads
    pydase.server.web_server.api.v1.endpoints.Serializer = (
        icon.serialization.IconSerializer
    )


def _level_from_verbosity(v: int) -> int:
    level = logging.WARNING - 10 * v
    return min(max(level, logging.DEBUG), logging.CRITICAL)


def start_server() -> None:
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from icon.server.utils.types import UpdateQueue
    import multiprocessing
    from pathlib import Path

    import icon.server.shared_resource_manager
    import icon.server.web_server.icon_server
    from icon.config.config import get_config
    from icon.server.api.api_service import APIService
    from icon.server.data_access.db_context.sqlite.migrations import run_migrations
    from icon.server.hardware_processing.worker import (
        HardwareProcessingWorker,
    )
    from icon.server.post_processing.worker import PostProcessingWorker
    from icon.server.pre_processing.worker import PreProcessingWorker
    from icon.server.scheduler.scheduler import Scheduler
    from icon.server.web_server.sio_setup import patch_sio_setup

    patch_sio_setup()
    patch_serialization_methods()
    run_migrations()

    scheduler = Scheduler(
        pre_processing_queue=icon.server.shared_resource_manager.pre_processing_queue
    )
    scheduler.start()

    number_of_pre_processing_workers = get_config().server.pre_processing.workers
    pre_processing_update_queues: list[multiprocessing.Queue[UpdateQueue]] = [
        multiprocessing.Queue() for _ in range(number_of_pre_processing_workers)
    ]

    for i, queue in enumerate(pre_processing_update_queues):
        PreProcessingWorker(
            worker_number=i,
            hardware_processing_queue=icon.server.shared_resource_manager.hardware_processing_queue,
            pre_processing_queue=icon.server.shared_resource_manager.pre_processing_queue,
            update_queue=queue,
            manager=icon.server.shared_resource_manager.manager,
        ).start()

    hardware_processing_worker = HardwareProcessingWorker(
        hardware_processing_queue=icon.server.shared_resource_manager.hardware_processing_queue,
        post_processing_queue=icon.server.shared_resource_manager.post_processing_queue,
        manager=icon.server.shared_resource_manager.manager,
    )
    hardware_processing_worker.start()

    post_processing_worker = PostProcessingWorker(
        post_processing_queue=icon.server.shared_resource_manager.post_processing_queue,
    )
    post_processing_worker.start()

    icon.server.web_server.icon_server.IconServer(
        APIService(pre_processing_event_queues=pre_processing_update_queues),
        host=get_config().server.host,
        web_port=get_config().server.port,
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
def main(version: bool, verbose: int, quiet: int, config: pathlib.Path) -> None:
    """Start the ICON server"""

    if version:
        from importlib.metadata import distribution

        __version__ = distribution("icon").version
        click.echo(f"icon {__version__}")
        raise SystemExit(0)

    level = _level_from_verbosity(verbose - quiet)
    setup_logging(level)

    set_config_path(config or pathlib.Path.home() / ".config/icon/config.yaml")
    start_server()


if __name__ == "__main__":
    main()
