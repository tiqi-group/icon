from collections.abc import AsyncGenerator
from http import HTTPStatus

import aiohttp.web
import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from icon.server.web_server.visualiser import (
    DIST_DIR,
    _visualiser_file_response,
    visualiser_middleware,
)


async def _catch_all(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Mimics pydase's catch-all index route, which matches every path."""
    return aiohttp.web.Response(text="icon index")


@pytest_asyncio.fixture(loop_scope="function")
async def client() -> AsyncGenerator[
    TestClient[aiohttp.web.Request, aiohttp.web.Application], None
]:
    app = aiohttp.web.Application(middlewares=[visualiser_middleware])
    app.router.add_get(r"/{tail:.*}", _catch_all)
    async with TestClient(TestServer(app)) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_serves_index_html(
    client: TestClient[aiohttp.web.Request, aiohttp.web.Application],
) -> None:
    response = await client.get("/visualizer/")

    assert response.status == HTTPStatus.OK
    assert response.content_type == "text/html"
    assert "Visualising pulse sequences" in await response.text()


@pytest.mark.asyncio
async def test_redirects_prefix_without_trailing_slash(
    client: TestClient[aiohttp.web.Request, aiohttp.web.Application],
) -> None:
    response = await client.get("/visualizer", allow_redirects=False)

    assert response.status == HTTPStatus.MOVED_PERMANENTLY
    assert response.headers["Location"] == "/visualizer/"


@pytest.mark.asyncio
async def test_serves_static_asset(
    client: TestClient[aiohttp.web.Request, aiohttp.web.Application],
) -> None:
    response = await client.get("/visualizer/manifest.json")

    assert response.status == HTTPStatus.OK
    assert response.content_type == "application/json"


@pytest.mark.asyncio
async def test_spa_route_falls_back_to_index_html(
    client: TestClient[aiohttp.web.Request, aiohttp.web.Application],
) -> None:
    response = await client.get("/visualizer/plot")

    assert response.status == HTTPStatus.OK
    assert "Visualising pulse sequences" in await response.text()


@pytest.mark.asyncio
async def test_other_paths_fall_through_to_app_routes(
    client: TestClient[aiohttp.web.Request, aiohttp.web.Application],
) -> None:
    response = await client.get("/data")

    assert await response.text() == "icon index"


def test_path_traversal_is_not_served() -> None:
    response = _visualiser_file_response("/visualizer/../__init__.py")

    assert isinstance(response, aiohttp.web.FileResponse)
    assert response._path == DIST_DIR / "index.html"
