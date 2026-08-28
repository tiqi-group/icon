import asyncio
from typing import Any, cast

import pydase
from pydase.client.proxy_loader import ProxyLoader


def raw_client_call(client: pydase.Client, event: str, data: Any, timeout: int) -> Any:
    """Perform a socket.io call on a pydase client with a custom timeout.

    pydase's ``Client.update_value``/``get_value`` are hard-wired to
    python-socketio's default 60 s call timeout, which is too short for slow
    device setters, so this replicates them with a configurable timeout.
    Returns the raw (still serialized) response.

    This is a blocking call: it waits on the client's dedicated event loop
    thread and should be run off the caller's own event loop (e.g. via
    ``asyncio.to_thread``) if the caller is itself async.
    """
    loop = client._loop
    if loop is None:
        raise RuntimeError("pydase client is not connected")

    async def _call() -> Any:
        return await client._sio.call(event, data, timeout=timeout)

    return asyncio.run_coroutine_threadsafe(_call(), loop=loop).result()


def client_call_with_timeout(
    client: pydase.Client, event: str, data: Any, timeout: int
) -> Any:
    """Like [`raw_client_call`][icon.server.utils.pydase_client.raw_client_call].

    Additionally deserializes the response, re-raising any exception reported
    by the device service.
    """
    result = raw_client_call(client, event, data, timeout)
    if result is not None:
        return ProxyLoader.loads_proxy(
            serialized_object=result,
            sio_client=client._sio,
            loop=cast("asyncio.AbstractEventLoop", client._loop),
        )
    return None
