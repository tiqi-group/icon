import logging
from collections.abc import Generator
from typing import Any

import pytest
import pytest_docker.plugin
import requests
import urllib3.exceptions

from icon.server.data_access.db_context import influxdb

logger = logging.getLogger(__name__)


def is_responsive(url: str) -> bool:
    ok = 200

    try:
        response = requests.get(url)
        if response.status_code == ok:
            return True
    except (requests.exceptions.ConnectionError, urllib3.exceptions.ProtocolError):
        pass
    return False


@pytest.fixture(scope="session")
def influxdb_service(
    docker_ip: str, docker_services: pytest_docker.plugin.Services
) -> str:
    """Ensure that HTTP service is up and responsive."""

    port = 8086
    url = f"http://{docker_ip}:{port}"
    docker_services.wait_until_responsive(
        timeout=10.0, pause=0.1, check=lambda: is_responsive(url)
    )
    return url


@pytest.fixture
def influxdb_session(
    influxdb_service: str,
) -> Generator[influxdb.InfluxDBSession, Any, None]:
    with influxdb.InfluxDBSession() as session:
        yield session


def test_read_and_write(influxdb_session: influxdb.InfluxDBSession) -> None:
    influxdb_session.write(
        "testing",
        {
            "measurement": "test",
            "fields": {
                "foo": 0,
                "bar": 1337,
            },
            "tags": {"foo": "bar"},
        },
    )

    results = influxdb_session.query_last(
        bucket="testing", measurement="test", fields={"foo"}
    )

    assert len(results) == 1

    result = results[0]
    expected_result = {
        "measurement": "test",
        "field": "foo",
        "value": 0,
        "tags": {"foo": "bar"},
        "time": result["time"],
    }
    assert result == expected_result
