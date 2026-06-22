import logging
from typing import Any

import pydase
from confz import DataSource

from icon.config.config import get_config, save_config
from icon.config.latest import ServiceConfig
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


class ConfigurationController(pydase.DataService):
    """Controller for managing and updating the application's configuration.

    This class provides an API to get and update the configuration, validate it, and
    save the updated configuration back to the source file.
    """

    def get_config(self) -> dict[str, Any]:
        """Get current configuration dictionary."""
        return get_config().model_dump()

    def update_config_option(self, key: str, value: Any) -> bool:
        """Update a specific configuration option.

        Traverses the configuration using the dot-separated key, updates the specified
        value, validates the entire configuration, and saves the changes.

        Args:
            key:
                The dot-separated key of the configuration option (e.g.,
                "experiment_library.git_repository").
            value:
                The new value for the configuration option.

        Returns:
            True if the update is successful, False otherwise.
        """
        try:
            current_config = get_config().model_dump()
            set_nested(current_config, key, value)

            # Validate the updated configuration
            updated_config = ServiceConfig(config_sources=DataSource(current_config))

            # Save the updated configuration back to the file
            save_config(updated_config)
            emit_queue.put(
                {"event": "config.update", "data": updated_config.model_dump()}
            )
        except KeyError:
            logger.exception("Failed to update configuration")
            return False
        return True


def set_nested(config: dict[str, Any], nested_key: str, value: Any) -> None:
    """Set a value in a nested dict."""
    current: dict[str, Any] | list[Any] = config
    *fields, last_field = parse_config_key(nested_key)
    # Traverse to the nested key
    for field in fields:
        if isinstance(current, dict) and (
            not isinstance(field, str) or field not in current
        ):
            raise KeyError(f"Key {nested_key!r} not found in configuration.")
        if isinstance(current, list) and (
            not isinstance(field, int) or field >= len(current)
        ):
            raise IndexError(
                f"Configuration error: Index out of range: {field} in {nested_key!r}"
            )
        current = current[field]  # type: ignore[index]

    # Update the value
    current[last_field] = value  # type: ignore[index]


def parse_config_key(nested_key: str) -> list[str | int]:
    components = nested_key.split(".")

    def split_index(key: str) -> tuple[str | int, ...]:
        try:
            key, index_str = key.removesuffix("]").split("[", 1)
            return key, int(index_str)
        except ValueError:
            return (key,)

    return [c for pair in components for c in pair]
