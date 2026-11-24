"""Serves the sequence-visualizer build under ``/visualizer/``.

The files in ``src/icon/server/frontend_visualizer/`` are a build of the
ionpulse-sequence-visualiser, produced by the frontend build (see
frontend/README.md).

The files are served by a middleware, see ``icon_web_server.py``.
"""

from pathlib import Path

import aiohttp.typedefs
import aiohttp.web

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
