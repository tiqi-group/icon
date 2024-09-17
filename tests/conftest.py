import pytest


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.rootpath / "docker/docker-compose.yml")


@pytest.fixture(scope="session")
def docker_compose_command() -> str:
    return "podman-compose"
