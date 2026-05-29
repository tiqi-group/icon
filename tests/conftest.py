# ruff: noqa: PLC0415
from __future__ import annotations

import logging
import os
import pathlib

import pytest

from icon.config.config_path import set_config_path
from icon.logging import setup_logging
from icon.server.api.configuration_controller import ConfigurationController

_testdir = pathlib.Path(__file__).parent
_testdb = _testdir / "test_db.db"

def pytest_configure() -> None:
    set_config_path(_testdir / "test_config.yaml")
    log_level_name = os.environ.get("TEST_LOG_LEVEL", "ERROR").upper()
    setup_logging(getattr(logging, log_level_name, logging.DEBUG))

    cc = ConfigurationController()
    cc.update_config_option("databases.sqlite.file", str(_testdb))

def new_testdb() -> None:
    _testdb.unlink(missing_ok=True)  # Remove existing test DB if it exists
    from icon.server.data_access.db_context.sqlite.engine import engine
    assert engine.url.database is not None and str(_testdb) in engine.url.database, "SQLite engine should be configured to use the test database."  # noqa: PT018
    from icon.server.data_access.db_context.sqlite.migrations import run_migrations  # noqa: I001
    run_migrations()
    engine.dispose()

@pytest.fixture(scope="module", autouse=True)
def new_testdb_fixture() -> None:
    new_testdb()

@pytest.fixture(autouse=True)
def clean_testdb() -> None:
    """Clear all tables before each test to ensure isolation."""
    from icon.server.data_access.db_context.sqlite import engine
    from icon.server.data_access.models.sqlite import Base

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
