"""Tests for how `ParametersRepository` selects its InfluxDB parameter backend.

The layout each backend reads and writes is covered in
``tests/server/data_access/db_context/test_parameters_backend_v2.py`` and by the
container-marked InfluxDB v1 tests; what matters here is that the configured
deployment picks the right backend, and that an InfluxDB v2 deployment never reaches
for the v1 schema detection (which would dial the v1 host).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from icon.server.data_access.db_context.influxdb.parameters_backend import (
    InfluxDBv2ParameterBackend,
    ParameterBackendR1,
    ParameterDBSchema,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

TEST_CONFIG = Path(__file__).parents[3] / "config.yaml"


@pytest.fixture
def _reset_backend() -> Iterator[None]:
    """Drop the cached backend around a test, as it is resolved once per process."""
    ParametersRepository._backend = None
    yield
    ParametersRepository._backend = None


def config_with_backend(tmp_path: Path, backend: str) -> str:
    """Write a copy of the test config that selects *backend*."""
    config = yaml.safe_load(TEST_CONFIG.read_text())
    config["databases"]["backend"] = backend
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    return str(path)


@pytest.mark.usefixtures("_reset_backend")
def test_influxdbv2_config_selects_the_v2_r2_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ICON_CONFIG", config_with_backend(tmp_path, "influxdbv2"))

    backend = ParametersRepository._get_backend()

    assert isinstance(backend, InfluxDBv2ParameterBackend)
    assert backend.schema is ParameterDBSchema.R2
    assert backend.measurement.startswith("icon|2|")


@pytest.mark.usefixtures("_reset_backend")
def test_influxdbv1_config_still_detects_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ICON_CONFIG", config_with_backend(tmp_path, "influxdbv1"))
    monkeypatch.setattr(
        "icon.server.data_access.repositories.parameters_repository"
        ".assert_parameter_db",
        lambda **_: ParameterDBSchema.R1,
    )

    assert isinstance(ParametersRepository._get_backend(), ParameterBackendR1)
