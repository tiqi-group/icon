from types import TracebackType

import redis

from icon.config.config import get_config


class ValkeySession:
    def __init__(self) -> None:
        self._config = get_config().databases.valkey
        self.client = redis.Redis(host=self._config.host, port=self._config.port)

    def __enter__(self) -> redis.Redis:
        return self.client

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        self.client.close()  # type: ignore
