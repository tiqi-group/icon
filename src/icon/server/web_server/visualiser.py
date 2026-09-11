"""Serves the sequence-visualizer build under ``/visualizer/``.

The files in ``src/icon/server/frontend_visualizer/`` are a build of the
ionpulse-sequence-visualiser, produced by the frontend build (see
frontend/README.md).

pydase's ``WebServer`` constructs and runs its aiohttp application inside
``serve()`` without an extension hook, and its catch-all index route swallows
every path. The application object only becomes reachable when ``serve()``
hands it to ``aiohttp.web._run_app``, so ``IconWebServer`` wraps that call to
attach a middleware which serves the visualizer files before route handlers
run.
"""

from pathlib import Path
from typing import Any

import aiohttp.typedefs
import aiohttp.web
from pydase.server.web_server import WebServer

URL_PREFIX = "/visualizer"
DIST_DIR = (Path(__file__).parent.parent / "frontend_visualizer").resolve()


def _visualiser_file_response(url_path: str) -> aiohttp.web.StreamResponse:
    relative_path = url_path[len(URL_PREFIX) :].lstrip("/")
    file = (DIST_DIR / relative_path).resolve()

    if not file.is_relative_to(DIST_DIR) or not file.is_file():
        # Client-side routes of the visualizer SPA (e.g. /visualizer/plot) must
        # fall back to its index.html, mirroring the nginx setup in its README.
        file = DIST_DIR / "index.html"

    if not file.is_file():
        return aiohttp.web.Response(
            status=404,
            text=f"Sequence visualizer assets not found in {DIST_DIR}.",
        )

    return aiohttp.web.FileResponse(file)


@aiohttp.web.middleware
async def visualiser_middleware(
    request: aiohttp.web.Request,
    handler: aiohttp.typedefs.Handler,
) -> aiohttp.web.StreamResponse:
    if request.path == URL_PREFIX:
        # The visualizer is built with relative asset paths ("--base=./"), so
        # it must be served from a URL ending in a slash.
        raise aiohttp.web.HTTPMovedPermanently(f"{URL_PREFIX}/")
    if request.path.startswith(f"{URL_PREFIX}/"):
        return _visualiser_file_response(request.path)
    return await handler(request)


class IconWebServer(WebServer):
    """pydase ``WebServer`` that additionally serves the sequence visualizer."""

    async def serve(self) -> None:
        original_run_app = aiohttp.web._run_app

        async def run_app_with_visualiser(
            app: aiohttp.web.Application, **kwargs: Any
        ) -> None:
            app.middlewares.append(visualiser_middleware)
            await original_run_app(app, **kwargs)

        aiohttp.web._run_app = run_app_with_visualiser  # type: ignore[assignment]
        try:
            await super().serve()
        finally:
            aiohttp.web._run_app = original_run_app  # type: ignore[assignment]


def patch_web_server() -> None:
    """Make ``pydase.Server`` instantiate :class:`IconWebServer`."""
    import pydase.server.server  # noqa: PLC0415

    pydase.server.server.WebServer = IconWebServer  # type: ignore[misc]
