import logging

import pytest
import pytest_docker.plugin
import redis.asyncio.client

from icon.server.data_access.db_context import valkey

logger = logging.getLogger(__name__)


def is_responsive(host: str, port: int) -> bool:
    client = redis.Redis(host, port)
    return bool(client.ping())


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


@pytest.mark.asyncio(loop_scope="function")
async def test_read_and_write(valkey_service: tuple[str, int]) -> None:
    async with valkey.AsyncValkeySession() as valkey_session:
        await valkey_session.set("test", 1)
        assert await valkey_session.get("test") == "1"
