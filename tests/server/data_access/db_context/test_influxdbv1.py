import logging
import os
import socket
import time
from collections.abc import Iterable
from pathlib import Path

import pytest
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
def influxdbv1_service() -> Iterable[None]:
    """Ensure that influxdbv1 service is up and responsive."""

    def check_port(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Attempting to connect to localhost on the specified port
            return sock.connect_ex(("127.0.0.1", port)) == 0

    port = 8087
    logger.debug("http://localhost:%s", port)
    if not check_port(port):
        yml = Path(__file__).parent.parent.parent.parent.parent / "k8s" / "dev.yml"
        os.system(f"podman kube play {yml}")
        while not check_port(port):
            time.sleep(0.5)
        yield
        os.system(f"podman kube play --down {yml}")
    else:
        yield


def test_InfluxDBv1Session(influxdbv1_service: None) -> None:  # noqa: N802
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
