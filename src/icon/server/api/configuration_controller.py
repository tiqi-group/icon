import logging
from typing import Any

import pydase
import yaml
from confz import DataSource

from icon.config.config import get_config, get_config_source
from icon.config.v1 import ServiceConfigV1

logger = logging.getLogger(__file__)


class ConfigurationController(pydase.DataService):
    """A controller for managing and updating the application's configuration.

    This class provides an API to update the configuration, validate it, and save the
    updated configuration back to the source file.
    """

    def __init__(self) -> None:
        super().__init__()
        self._config_folder = get_config_source()
        self._config = get_config().model_dump()

    @property
    def config(self) -> dict[str, Any]:
        # TODO: changes to self._config are not picked up by pydase
        # (see https://github.com/tiqi-group/pydase/issues/187)
        return self._config

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
            current = self._config
            for field in fields[:-1]:
                if field not in current:
                    raise KeyError(f"Key {key!r} not found in configuration.")
                current = current[field]

            # Update the value
            current[fields[-1]] = value

            # Validate the updated configuration
            updated_config = ServiceConfigV1(config_sources=DataSource(self._config))

            # Save the updated configuration back to the file
            self._save_configuration(updated_config)
            return True
        except KeyError as e:
            logger.error("Failed to update configuration: %s", e)
            return False

    def _save_configuration(self, new_config: ServiceConfigV1) -> None:
        """Save the updated configuration to the source YAML file.

        Serializes the updated configuration and writes it back to the file.

        Args:
            new_config:
                The validated configuration instance.
        """

        with self._config_folder.open("w") as file:
            file.write(yaml.dump(new_config.model_dump()))
