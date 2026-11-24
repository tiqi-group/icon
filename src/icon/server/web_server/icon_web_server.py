"""pydase ``WebServer`` with ICON's additional HTTP routes.

pydase's ``WebServer`` constructs and runs its aiohttp application inside
``serve()`` without an extension hook, and its catch-all index route swallows
every path. The application object only becomes reachable when ``serve()``
hands it to ``aiohttp.web._run_app``, so ``IconWebServer`` wraps that call to
attach middlewares which serve ICON's own paths before route handlers run.
"""

from typing import Any

import aiohttp.web
from pydase.server.web_server import WebServer

from icon.server.web_server.user_styles import user_styles_middleware
from icon.server.web_server.visualiser import visualiser_middleware


class IconWebServer(WebServer):
    """pydase ``WebServer`` that also serves the visualizer and the user styles."""

    async def serve(self) -> None:
        original_run_app = aiohttp.web._run_app

        async def run_app_with_middlewares(
            app: aiohttp.web.Application, **kwargs: Any
        ) -> None:
            app.middlewares.append(visualiser_middleware)
            app.middlewares.append(user_styles_middleware)
            await original_run_app(app, **kwargs)

        aiohttp.web._run_app = run_app_with_middlewares  # type: ignore[assignment]
        try:
            await super().serve()
        finally:
            aiohttp.web._run_app = original_run_app  # type: ignore[assignment]


def patch_web_server() -> None:
    """Make ``pydase.Server`` instantiate :class:`IconWebServer`."""
    import pydase.server.server  # noqa: PLC0415

    pydase.server.server.WebServer = IconWebServer  # type: ignore[misc]
