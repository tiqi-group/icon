from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import click
from sqlalchemy.exc import SQLAlchemyError

from icon.config.config import get_config, set_config_path

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)

CLI_HELP = """Tool for moving result files into day folders.

Earlier versions of ICON stored every result file directly in the results
directory, named after the run's scheduled time. ICON now reads result files
only from one folder per day, named after the scheduled time in ISO 8601 basic
format and the experiment name, without the `:` and spaces that break on
Windows:

\b
<results_dir>/<yyyy-mm-dd>/<yyyymmdd>T<hhmmss.ffffff>_<experiment name>.h5

This tool moves and renames the files of the old flat layout. The experiment of
each file is looked up in the job database; files without a run there keep only
the scheduled time in their name. Files are moved, not copied, and other files
in the results directory are left alone. ICON refuses to start until this
migration is done, and must not run while it is performed.

Run with --dry-run first to see what would be moved.
"""


class _MigrationError(Exception):
    """A problem that stops the migration before any file is moved."""


def _plan(results_dir: Path) -> list[tuple[Path, Path]]:
    """Return `(path, destination)` for each result file in the flat layout.

    Raises:
        _MigrationError: The job database cannot be read, or has no run for any
            of the files, which suggests it is not the one ICON writes to.
    """
    # Imported here: see `run_migration`.
    from icon.server.data_access.repositories.experiment_data_repository import (  # noqa: PLC0415
        find_flat_result_files,
        result_path,
    )
    from icon.server.data_access.repositories.job_run_repository import (  # noqa: PLC0415
        JobRunRepository,
        ScheduledRun,
    )

    flat = find_flat_result_files(results_dir)
    if not flat:
        return []

    database = get_config().databases.sqlite.file
    try:
        runs = JobRunRepository.get_scheduled_runs()
    except SQLAlchemyError as exc:
        raise _MigrationError(
            f"Cannot read the job database {database!r}: {exc}"
        ) from exc
    experiment_ids: dict[datetime, str] = dict(runs)
    if not any(scheduled_time in experiment_ids for _, scheduled_time in flat):
        raise _MigrationError(
            f"None of the {len(flat)} flat result file(s) has a run in the job "
            f"database {database!r}. Check that --config points to the config "
            "ICON runs with."
        )

    plan = []
    for path, scheduled_time in flat:
        experiment_id = experiment_ids.get(scheduled_time)
        if experiment_id is None:
            logger.warning(
                "%s has no run in the job database; its new name has no "
                "experiment name.",
                path.name,
            )
        # An empty experiment ID leaves the experiment name out.
        run = ScheduledRun(scheduled_time, experiment_id or "")
        plan.append((path, result_path(results_dir, run)))
    return plan


def _movable_files(plan: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    """Return the files whose destination is free; the others are never overwritten."""
    movable = []
    for path, dest in plan:
        if dest.exists():
            logger.error("Cannot move %s: %s already exists.", path.name, dest)
        else:
            movable.append((path, dest))
    return movable


def _move_files(moves: list[tuple[Path, Path]], results_dir: Path) -> int:
    """Move each file to its destination and return how many were moved."""
    moved = 0
    for path, dest in moves:
        try:
            dest.parent.mkdir(exist_ok=True)
            path.rename(dest)
        except OSError as exc:
            logger.error("Cannot move %s: %s", path.name, exc)  # noqa: TRY400
        else:
            moved += 1
            logger.debug("Moved %s -> %s", path.name, dest.relative_to(results_dir))
    return moved


def run_migration(*, dry_run: bool, yes: bool) -> int:
    # Imported here: importing the repositories reads the config and opens the
    # job database, which must happen after `--config` is applied.
    from icon.server.data_access.repositories.experiment_data_repository import (  # noqa: PLC0415
        ResultsDirectoryNotFoundError,
        find_flat_result_files,
        require_results_dir,
    )

    try:
        results_dir = require_results_dir()
        plan = _plan(results_dir)
    except (ResultsDirectoryNotFoundError, _MigrationError) as exc:
        logger.error("%s", exc)  # noqa: TRY400
        return 1

    if not plan:
        logger.info(
            "Nothing to migrate: %r has no flat result files.", str(results_dir)
        )
        return 0

    movable = _movable_files(plan)

    if dry_run:
        for path, dest in movable:
            logger.info("Would move %s -> %s", path.name, dest.relative_to(results_dir))
        logger.info(
            "Would move %d of %d flat result file(s) in %r (DRY RUN).",
            len(movable),
            len(plan),
            str(results_dir),
        )
        return 0 if len(movable) == len(plan) else 1

    if (
        movable
        and not yes
        and not click.confirm(
            f"Move {len(movable)} result file(s) in {str(results_dir)!r} into day folders?",
            default=False,
        )
    ):
        logger.info("Migration cancelled.")
        return 1

    moved = _move_files(movable, results_dir)
    logger.info(
        "Moved %d of %d flat result file(s) into day folders.", moved, len(plan)
    )

    if remaining := find_flat_result_files(results_dir):
        logger.error(
            "%d flat result file(s) remain in %r; ICON will not start until they "
            "are moved.",
            len(remaining),
            str(results_dir),
        )
        return 1
    return 0


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=CLI_HELP,
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to the ICON config file to use (defaults to $ICON_CONFIG, else "
    "~/.config/icon/config.yaml).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be moved without changing anything.",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Skip the interactive confirmation prompt.",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging.")
def cli(config_path: Path | None, dry_run: bool, yes: bool, verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    )

    if config_path is not None:
        set_config_path(config_path)

    raise SystemExit(run_migration(dry_run=dry_run, yes=yes))


if __name__ == "__main__":
    cli()
