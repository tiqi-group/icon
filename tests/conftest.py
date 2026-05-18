import pathlib
import pytest
from icon.config.config_path import set_config_path
from icon.server.api.configuration_controller import ConfigurationController


def pytest_configure(config):
    """Initialize test database before tests are run."""

    testdir = pathlib.Path(__file__).parent
    set_config_path(testdir / "test_config.yaml")

    testdb = testdir / "test_db.db"
    testdb.unlink(missing_ok=True)  # Remove existing test DB if it exists

    cc = ConfigurationController()
    cc.update_config_option("databases.sqlite.file", str(testdb))

    from icon.server.data_access.db_context.sqlite.migrations import run_migrations
    run_migrations()
