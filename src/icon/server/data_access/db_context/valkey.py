from types import TracebackType

import redis.asyncio

from icon.config.config import get_config


class AsyncValkeySession:
    def __init__(self) -> None:
        self._config = get_config().databases.valkey
        self.client = redis.asyncio.Redis(
            host=self._config.host,
            port=self._config.port,
            decode_responses=True,
        )

    async def __aenter__(self) -> redis.asyncio.Redis:
        return self.client

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        await self.client.aclose()
