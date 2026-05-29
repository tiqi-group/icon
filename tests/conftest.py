from __future__ import annotations

import pathlib
import logging
import pytest

from icon.config.config_path import set_config_path
from icon.server.api.configuration_controller import ConfigurationController
from icon.logging import setup_logging

from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from sqlalchemy import Engine

_testdir = pathlib.Path(__file__).parent
_testdb = _testdir / "test_db.db"

def pytest_configure(config: pytest.Config) -> None:
    set_config_path(_testdir / "test_config.yaml")
    setup_logging(logging.DEBUG)

    cc = ConfigurationController()
    cc.update_config_option("databases.sqlite.file", str(_testdb))
    # new_testdb()

def new_testdb() -> None:
    _testdb.unlink(missing_ok=True)  # Remove existing test DB if it exists
    from icon.server.data_access.db_context.sqlite.engine import engine
    assert engine.url.database is not None and str(_testdb) in engine.url.database, "SQLite engine should be configured to use the test database."
    from icon.server.data_access.db_context.sqlite.migrations import run_migrations
    run_migrations()
    engine.dispose()

@pytest.fixture(scope="module", autouse=True)
def new_testdb_fixture() -> None:
    new_testdb()

@pytest.fixture(scope="function", autouse=True)
def clean_testdb() -> None:
    """Clear all tables before each test to ensure isolation."""
    from icon.server.data_access.db_context.sqlite import engine
    from icon.server.data_access.models.sqlite import Base

    print("Cleaning test database...")
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
