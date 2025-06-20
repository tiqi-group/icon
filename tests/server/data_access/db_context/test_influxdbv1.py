import logging

import pytest
import pytest_docker.plugin
import requests

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import InfluxDBv1Session

logger = logging.getLogger(__name__)

SUCCESS = 200


def is_responsive(host: str, port: int) -> bool:
    try:
        response = requests.post(
            f"http://{host}:{port}/query?"
            f"u={get_config().databases.influxdbv1.username}"
            f"&p={get_config().databases.influxdbv1.password}",
            data={"q": "SHOW DATABASES"},
        )
    except Exception:
        return False
    return response.status_code == SUCCESS and "testing" in response.text


@pytest.fixture(scope="session")
def influxdbv1_service(
    docker_ip: str, docker_services: pytest_docker.plugin.Services
) -> tuple[str, int]:
    """Ensure that influxdbv1 service is up and responsive."""

    port = 8087
    logger.debug("http://%s:%s", docker_ip, port)
    docker_services.wait_until_responsive(
        timeout=10.0, pause=0.1, check=lambda: is_responsive(docker_ip, port)
    )

    return docker_ip, port


def test_InfluxDBv1Session(influxdbv1_service: tuple[str, int]) -> None:  # noqa: N802
    test_value = 1337

    with InfluxDBv1Session() as session:
        session.write_points(
            [
                {
                    "measurement": "Pytest",
                    "fields": {"test": test_value, "test1": test_value + 0.4},
                }
            ]
        )
        result = session.query(measurement="Pytest", field="test")

        assert result is not None and result["test"] == test_value

        assert session.query_last(measurement="Pytest") == {
            "test": test_value,
            "test1": test_value + 0.4,
        }
