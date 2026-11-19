"""Tests for `ParametersRepository.initialise`."""

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest
import requests

from icon.config.latest import InfluxDBv1Config
from icon.server.data_access.db_context.influxdb.parameters_backend import (
    ParameterDBSchema,
)
from icon.server.data_access.repositories import (
    parameters_repository as parameters_repository_module,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)

if TYPE_CHECKING:
    from multiprocessing.managers import DictProxy

    from icon.server.data_access.experiment_data import DatabaseValueType


@pytest.fixture
def repository() -> ParametersRepository:
    """A fresh repository bound to a plain in-test shared dict."""
    return ParametersRepository(
        shared_parameters=cast("DictProxy[str, DatabaseValueType]", {}),
        influx_config=InfluxDBv1Config(),
    )


def test_initialise_seeds_the_shared_dict(
    monkeypatch: pytest.MonkeyPatch, repository: ParametersRepository
) -> None:
    """The first call must succeed even though the repository is not initialised yet."""
    backend = MagicMock()
    backend.get_influxdb_parameters.return_value = {"namespace:group:param": 1.0}
    assert_parameter_db = MagicMock(return_value=ParameterDBSchema.R2)
    create_parameter_backend = MagicMock(return_value=backend)
    monkeypatch.setattr(
        parameters_repository_module, "assert_parameter_db", assert_parameter_db
    )
    monkeypatch.setattr(
        parameters_repository_module,
        "create_parameter_backend",
        create_parameter_backend,
    )

    repository.initialise()

    assert repository.initialised
    assert repository.get_shared_parameters() == {"namespace:group:param": 1.0}
    # The configured InfluxDB settings must be propagated to the backend factory.
    expected_config = InfluxDBv1Config()
    assert_parameter_db.assert_called_once_with(
        expected_config, wrap_connection_errors=False
    )
    create_parameter_backend.assert_called_once_with(
        ParameterDBSchema.R2, expected_config
    )


def test_initialise_influxdb_down(
    monkeypatch: pytest.MonkeyPatch, repository: ParametersRepository
) -> None:
    """A connection failure must propagate and must not mark the repository initialised."""

    def assert_parameter_db(
        influx: InfluxDBv1Config, *, wrap_connection_errors: bool = True
    ) -> ParameterDBSchema:
        raise requests.exceptions.ConnectionError(
            f"InfluxDB {influx.host}:{influx.port} is down (wrap={wrap_connection_errors})"
        )

    monkeypatch.setattr(
        parameters_repository_module, "assert_parameter_db", assert_parameter_db
    )

    with pytest.raises(requests.exceptions.ConnectionError):
        repository.initialise()

    assert not repository.initialised


def test_initialise_retry_after_failure(
    monkeypatch: pytest.MonkeyPatch, repository: ParametersRepository
) -> None:
    """A retry must succeed once InfluxDB is reachable."""
    backend = MagicMock()
    backend.get_influxdb_parameters.return_value = {"namespace:group:param": 2.0}
    create_parameter_backend = MagicMock(return_value=backend)
    monkeypatch.setattr(
        parameters_repository_module,
        "create_parameter_backend",
        create_parameter_backend,
    )
    attempts: dict[str, Any] = {"n": 0}

    def assert_parameter_db(
        influx: InfluxDBv1Config, *, wrap_connection_errors: bool = True
    ) -> ParameterDBSchema:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise requests.exceptions.ConnectionError(f"InfluxDB {influx.host} is down")
        assert not wrap_connection_errors
        return ParameterDBSchema.R2

    monkeypatch.setattr(
        parameters_repository_module, "assert_parameter_db", assert_parameter_db
    )

    with pytest.raises(requests.exceptions.ConnectionError):
        repository.initialise()
    assert not repository.initialised

    repository.initialise()

    assert repository.initialised
    assert repository.get_shared_parameters() == {"namespace:group:param": 2.0}
