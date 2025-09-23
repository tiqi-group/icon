import logging
from typing import Any

import pydase
import yaml
from confz import DataSource

from icon.config.config import get_config
from icon.config.config_path import get_config_path
from icon.config.v1 import ServiceConfigV1
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__file__)


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
            # Traverse to the nested key
            fields = key.split(".")
            current_config = get_config().model_dump()
            current = current_config
            for field in fields[:-1]:
                if field not in current:
                    raise KeyError(f"Key {key!r} not found in configuration.")
                current = current[field]

            # Update the value
            current[fields[-1]] = value

            # Validate the updated configuration
            updated_config = ServiceConfigV1(config_sources=DataSource(current_config))

            # Save the updated configuration back to the file
            self._save_configuration(updated_config)
            emit_queue.put(
                {"event": "config.update", "data": updated_config.model_dump()}
            )
            return True
        except KeyError as e:
            logger.exception("Failed to update configuration: %s", e)
            return False

    def _save_configuration(self, new_config: ServiceConfigV1) -> None:
        """Save the updated configuration to the source YAML file.

        Serializes the updated configuration and writes it back to the file.

        Args:
            new_config:
                The validated configuration instance.
        """

        with get_config_path().open("w") as file:
            file.write(yaml.dump(new_config.model_dump()))
