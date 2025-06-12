import logging
import time
from typing import Literal, overload

import socketio

from icon.server.utils.valkey import is_valkey_available, valkey_url


class SocketIOManagerFactory:
    def __init__(self) -> None:
        self._instance: socketio.RedisManager | None = None
        self._wait_time = 1.0

    @overload
    def get(
        self, *, logger: logging.Logger, wait: Literal[True]
    ) -> socketio.RedisManager: ...

    @overload
    def get(
        self, *, logger: logging.Logger, wait: Literal[False] = False
    ) -> socketio.RedisManager | None: ...

    def get(
        self, *, logger: logging.Logger, wait: bool = False
    ) -> socketio.RedisManager | None:
        if self._instance is not None:
            return self._instance

        url = valkey_url()

        if wait:
            logger.info("Waiting until Valkey is available...")
            while not is_valkey_available():
                time.sleep(self._wait_time)
        elif not is_valkey_available():
            logger.warning("Valkey not available")
            return None

        self._instance = socketio.RedisManager(url=url, write_only=True, logger=logger)
        return self._instance
