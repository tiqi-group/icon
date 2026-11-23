from collections.abc import AsyncGenerator
from http import HTTPStatus
from pathlib import Path

import aiohttp.web
import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from icon.server.web_server.user_styles import (
    _style_file_response,
    user_styles_middleware,
)

Client = TestClient[aiohttp.web.Request, aiohttp.web.Application]


async def _catch_all(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Mimics pydase's catch-all index route, which matches every path."""
    return aiohttp.web.Response(text="icon index")


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ICON_CONFIG", str(tmp_path / "config.yaml"))
    return tmp_path


@pytest_asyncio.fixture(loop_scope="function")
async def client(config_dir: Path) -> AsyncGenerator[Client, None]:  # noqa: ARG001
    app = aiohttp.web.Application(middlewares=[user_styles_middleware])
    app.router.add_get(r"/{tail:.*}", _catch_all)
    async with TestClient(TestServer(app)) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_lists_no_styles_without_styles_dir(client: Client) -> None:
    response = await client.get("/styles/")

    assert response.status == HTTPStatus.OK
    assert await response.json() == []


@pytest.mark.asyncio
async def test_lists_directories_with_entry_point(
    client: Client, config_dir: Path
) -> None:
    for name in ("compact", "an operator style"):
        (config_dir / "styles" / name).mkdir(parents=True)
        (config_dir / "styles" / name / "index.css").touch()
    (config_dir / "styles" / "no-entry-point").mkdir()
    (config_dir / "styles" / "loose.css").touch()

    response = await client.get("/styles/")

    assert await response.json() == ["an operator style", "compact"]


@pytest.mark.asyncio
async def test_serves_style_files(client: Client, config_dir: Path) -> None:
    style = config_dir / "styles" / "an operator style"
    (style / "parts").mkdir(parents=True)
    (style / "index.css").write_text('@import "./parts/base.css";')
    (style / "parts" / "base.css").write_text("body { color: red; }")

    index = await client.get("/styles/an%20operator%20style/index.css")
    imported = await client.get("/styles/an%20operator%20style/parts/base.css")

    assert index.status == HTTPStatus.OK
    assert index.content_type == "text/css"
    assert index.headers["Cache-Control"] == "no-cache"
    assert await imported.text() == "body { color: red; }"


@pytest.mark.asyncio
async def test_missing_file_is_not_found(client: Client) -> None:
    response = await client.get("/styles/compact/index.css")

    assert response.status == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_serves_symlinked_style(
    client: Client, config_dir: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    shared = tmp_path_factory.mktemp("shared") / "compact"
    shared.mkdir()
    (shared / "index.css").write_text("body { color: red; }")
    (config_dir / "styles").mkdir()
    (config_dir / "styles" / "compact").symlink_to(shared)

    listing = await client.get("/styles/")
    index = await client.get("/styles/compact/index.css")

    assert await listing.json() == ["compact"]
    assert await index.text() == "body { color: red; }"


@pytest.mark.parametrize("path", ["../config.yaml", "compact/../../config.yaml"])
def test_does_not_serve_files_outside_styles_dir(config_dir: Path, path: str) -> None:
    (config_dir / "styles" / "compact").mkdir(parents=True)
    (config_dir / "config.yaml").write_text("secret")

    # HTTP clients normalise "..", so the guard is checked on the handler itself
    response = _style_file_response(path)

    assert response.status == HTTPStatus.NOT_FOUND


def test_does_not_serve_absolute_paths(config_dir: Path) -> None:
    (config_dir / "config.yaml").write_text("secret")

    response = _style_file_response(str(config_dir / "config.yaml"))

    assert response.status == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_other_paths_reach_the_application(client: Client) -> None:
    response = await client.get("/stylesheet")

    assert await response.text() == "icon index"
