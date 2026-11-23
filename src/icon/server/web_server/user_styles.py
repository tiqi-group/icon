"""Serves user-provided stylesheets under ``/styles/``.

A style is a subdirectory of ``styles/`` next to the configuration file that
contains an ``index.css``. ``/styles/`` lists the style names, and
``/styles/<name>/<path>`` serves the files of a style.
"""

from pathlib import Path, PurePosixPath

import aiohttp.typedefs
import aiohttp.web

from icon.config.config import get_config_path

URL_PREFIX = "/styles"
ENTRY_POINT = "index.css"


def get_styles_dir() -> Path:
    return (get_config_path().parent / "styles").resolve()


def list_styles() -> list[str]:
    styles_dir = get_styles_dir()
    if not styles_dir.is_dir():
        return []
    return sorted(
        style.name for style in styles_dir.iterdir() if (style / ENTRY_POINT).is_file()
    )


def _style_file_response(relative_path: str) -> aiohttp.web.StreamResponse:
    path = PurePosixPath(relative_path)
    file = get_styles_dir() / path

    # Symlinks may lead out of the styles directory, the requested path may not
    if path.is_absolute() or ".." in path.parts or not file.is_file():
        return aiohttp.web.Response(status=404, text="Style file not found.")

    # Styles are edited in place, so the browser must not serve stale copies.
    return aiohttp.web.FileResponse(file, headers={"Cache-Control": "no-cache"})


@aiohttp.web.middleware
async def user_styles_middleware(
    request: aiohttp.web.Request,
    handler: aiohttp.typedefs.Handler,
) -> aiohttp.web.StreamResponse:
    if request.path in (URL_PREFIX, f"{URL_PREFIX}/"):
        return aiohttp.web.json_response(list_styles())
    if request.path.startswith(f"{URL_PREFIX}/"):
        return _style_file_response(request.path[len(URL_PREFIX) + 1 :])
    return await handler(request)
