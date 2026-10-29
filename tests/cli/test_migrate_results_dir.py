from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from sqlalchemy.exc import OperationalError

from icon.cli import migrate_results_dir
from icon.cli.migrate_results_dir import cli
from icon.config import latest
from icon.server.data_access.repositories import experiment_data_repository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
    ScheduledRun,
)

RUNS = [
    # Naive, like the scheduled times read back from SQLite.
    ScheduledRun(datetime(2026, 3, 24, 23, 59), "mod.Ramsey (Ramsey fine)"),  # noqa: DTZ001
    ScheduledRun(datetime(2026, 3, 25, 0, 0, 0, 123456), "mod.Rabi (Rabi: 729)"),  # noqa: DTZ001
]
FLAT_FILES = {
    "2026-03-24 23:59:00.h5": "2026-03-24/20260324T235900.000000_Ramsey_fine.h5",
    "2026-03-25 00:00:00.123456.h5": "2026-03-25/20260325T000000.123456_Rabi_729.h5",
}


@pytest.fixture
def results_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a results directory in the flat layout, next to unrelated files."""
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(tmp_path)),
        databases=latest.DatabaseConfig(),
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)
    monkeypatch.setattr(migrate_results_dir, "get_config", lambda: config)
    monkeypatch.setattr(JobRunRepository, "get_scheduled_runs", lambda: RUNS)
    for name in FLAT_FILES:
        (tmp_path / name).write_text(name)
    (tmp_path / "analysis.h5").touch()
    # A day folder that already holds a file written after the upgrade.
    (tmp_path / "2026-03-24").mkdir()
    (tmp_path / "2026-03-24" / "20260324T080000.000000_Rabi.h5").touch()
    return tmp_path


def test_moves_and_renames_flat_result_files(results_dir: Path) -> None:
    result = CliRunner().invoke(cli, ["--yes"])

    assert result.exit_code == 0
    for name, destination in FLAT_FILES.items():
        assert not (results_dir / name).exists()
        assert (results_dir / destination).read_text() == name
    assert (results_dir / "2026-03-24" / "20260324T080000.000000_Rabi.h5").is_file()
    assert (results_dir / "analysis.h5").is_file()
    experiment_data_repository.require_day_folder_layout(results_dir)


def test_file_without_run_keeps_only_the_time(
    results_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(JobRunRepository, "get_scheduled_runs", lambda: RUNS[:1])

    result = CliRunner().invoke(cli, ["--yes"])

    assert result.exit_code == 0
    assert (results_dir / "2026-03-25" / "20260325T000000.123456.h5").is_file()


def test_no_file_with_a_run_aborts(
    results_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Most likely the config points at another ICON instance's database.
    monkeypatch.setattr(JobRunRepository, "get_scheduled_runs", list)

    result = CliRunner().invoke(cli, ["--yes"])

    assert result.exit_code == 1
    for name in FLAT_FILES:
        assert (results_dir / name).is_file()


def test_unreadable_database_aborts(
    results_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def get_scheduled_runs() -> list[ScheduledRun]:
        raise OperationalError("SELECT", {}, Exception("no such table: job_runs"))

    monkeypatch.setattr(JobRunRepository, "get_scheduled_runs", get_scheduled_runs)

    result = CliRunner().invoke(cli, ["--yes"])

    assert result.exit_code == 1
    for name in FLAT_FILES:
        assert (results_dir / name).is_file()


def test_dry_run_moves_nothing(results_dir: Path) -> None:
    result = CliRunner().invoke(cli, ["--dry-run"])

    assert result.exit_code == 0
    for name in FLAT_FILES:
        assert (results_dir / name).is_file()
    assert not (results_dir / "2026-03-25").exists()


def test_declined_confirmation_moves_nothing(results_dir: Path) -> None:
    result = CliRunner().invoke(cli, [], input="n\n")

    assert result.exit_code == 1
    for name in FLAT_FILES:
        assert (results_dir / name).is_file()


def test_existing_destination_is_not_overwritten(results_dir: Path) -> None:
    name = "2026-03-24 23:59:00.h5"
    (results_dir / FLAT_FILES[name]).write_text("newer")

    result = CliRunner().invoke(cli, ["--yes"])

    assert result.exit_code == 1
    assert (results_dir / name).read_text() == name
    assert (results_dir / FLAT_FILES[name]).read_text() == "newer"
    # The other file is still moved.
    assert (results_dir / FLAT_FILES["2026-03-25 00:00:00.123456.h5"]).is_file()


def test_nothing_to_migrate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(data=latest.DataConfiguration(results_dir=str(tmp_path)))
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    assert CliRunner().invoke(cli, ["--yes"]).exit_code == 0


def test_missing_results_dir_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(
        data=latest.DataConfiguration(results_dir=str(tmp_path / "missing"))
    )
    monkeypatch.setattr(experiment_data_repository, "get_config", lambda: config)

    assert CliRunner().invoke(cli, ["--yes"]).exit_code == 1
