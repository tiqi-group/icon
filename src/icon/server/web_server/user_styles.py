"""Serves stylesheets for the web interface under ``/styles/``.

A style is a directory that contains an ``index.css``. Styles are shipped with
ICON in ``icon/server/styles/`` and can be added in the user styles directory,
by default ``styles/`` next to the configuration file. A user style replaces an
included style of the same name. ``/styles/`` lists the style names, and
``/styles/<name>/<path>`` serves the files of a style.
"""

from pathlib import Path, PurePosixPath

import aiohttp.typedefs
import aiohttp.web

from icon.config.config import get_config, get_config_path

URL_PREFIX = "/styles"
ENTRY_POINT = "index.css"
INCLUDED_STYLES_DIR = Path(__file__).parent.parent / "styles"


def get_user_styles_dir() -> Path:
    configured = get_config().server.styles_dir
    if configured is not None:
        return Path(configured).expanduser()
    return get_config_path().parent / "styles"


def _styles_dirs() -> list[Path]:
    """Directories that contain styles, in order of precedence."""
    return [get_user_styles_dir(), INCLUDED_STYLES_DIR]


def list_styles() -> list[str]:
    return sorted(
        {
            style.name
            for styles_dir in _styles_dirs()
            if styles_dir.is_dir()
            for style in styles_dir.iterdir()
            if (style / ENTRY_POINT).is_file()
        }
    )


def _style_file_response(relative_path: str) -> aiohttp.web.StreamResponse:
    not_found = aiohttp.web.Response(status=404, text="Style file not found.")
    path = PurePosixPath(relative_path)

    # Symlinks may lead out of the styles directory, the requested path may not
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return not_found

    for styles_dir in _styles_dirs():
        if (styles_dir / path.parts[0] / ENTRY_POINT).is_file():
            file = styles_dir / path
            if not file.is_file():
                return not_found
            # Styles are edited in place, so the browser must not serve stale copies
            return aiohttp.web.FileResponse(file, headers={"Cache-Control": "no-cache"})

    return not_found


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
