import logging
from collections.abc import Generator
from typing import Any

import pytest
import pytest_docker.plugin
import redis
from icon.server.data_access.db_context import valkey

logger = logging.getLogger(__name__)


def is_responsive(host: str, port: int) -> bool:
    client = redis.Redis(host, port)
    if client.ping():
        return True
    return False


@pytest.fixture(scope="session")
def valkey_service(
    docker_ip: str, docker_services: pytest_docker.plugin.Services
) -> tuple[str, int]:
    """Ensure that valkey service is up and responsive."""

    port = 6379
    logger.debug("http://%s:%s", docker_ip, port)
    docker_services.wait_until_responsive(
        timeout=10.0, pause=0.1, check=lambda: is_responsive(docker_ip, port)
    )
    return docker_ip, port


@pytest.fixture
def valkey_session(
    valkey_service: tuple[str, int],
) -> Generator[redis.Redis, Any, None]:
    with valkey.ValkeySession() as session:
        yield session


def test_read_and_write(valkey_session: redis.Redis) -> None:
    valkey_session.set("test", 1)
    assert valkey_session.get("test") == b"1"
