import logging
from collections.abc import Callable
from typing import Any


def handle_keyboard_interrupt(
    logger: logging.Logger,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    def wrapper(f: Callable[..., None]) -> Callable[..., None]:
        def handled_f(*args: Any, **kwargs: Any) -> None:
            try:
                f(*args, **kwargs)
            except KeyboardInterrupt:
                logger.info("Forced Exit")

        return handled_f

    return wrapper
