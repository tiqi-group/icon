import json
import logging
from typing import Any, Literal, TypedDict, overload

from icon.server.data_access.db_context.valkey import AsyncValkeySession
from icon.server.data_access.repositories.experiment_metadata_repository import (
    get_added_removed_and_updated_keys,
)
from icon.server.exceptions import ValkeyUnavailableError
from icon.server.utils.socketio_manager import emit_event
from icon.server.utils.valkey import is_valkey_available

logger = logging.getLogger(__name__)


class ParameterMetadata(TypedDict):
    display_name: str
    unit: str
    default_value: float | int
    min_value: float | None
    max_value: float | None
    allowed_values: list[Any] | None


class ParameterMetadataRepository:
    @staticmethod
    @overload
    async def get_parameter_metadata(
        *, deserialize: Literal[True] = True
    ) -> dict[str, ParameterMetadata]: ...

    @staticmethod
    @overload
    async def get_parameter_metadata(
        *, deserialize: Literal[False] = False
    ) -> dict[str, str]: ...

    @staticmethod
    async def get_parameter_metadata(
        *, deserialize: bool = True
    ) -> dict[str, str] | dict[str, ParameterMetadata]:
        if not is_valkey_available():
            raise ValkeyUnavailableError()

        async with AsyncValkeySession() as valkey:
            parameter_metadata_serialized: dict[str, str] = await valkey.hgetall(
                "parameter_metadata"
            )  # type: ignore

            if deserialize:
                return {
                    key: json.loads(value)
                    for key, value in parameter_metadata_serialized.items()
                }
            return parameter_metadata_serialized

    @staticmethod
    async def update_parameter_metadata(
        *,
        new_parameter_metadata: dict[str, ParameterMetadata],
        remove_unspecified: bool = True,
    ) -> None:
        if not is_valkey_available():
            raise ValkeyUnavailableError()

        cached_parameter_metadata_serialized = (
            await ParameterMetadataRepository.get_parameter_metadata(deserialize=False)
        )

        new_parameter_metadata_serialized = {
            key: json.dumps(value) for key, value in new_parameter_metadata.items()
        }

        async with AsyncValkeySession() as valkey:
            await valkey.hset(
                "parameter_metadata", mapping=new_parameter_metadata_serialized
            )  # type: ignore

            added_keys, removed_keys, updated_keys = get_added_removed_and_updated_keys(
                new_parameter_metadata,
                cached_parameter_metadata_serialized,
            )

            if remove_unspecified and removed_keys:
                await valkey.hdel("parameter_metadata", *removed_keys)  # type: ignore

        if removed_keys:
            emit_event(logger=logger, event="parameters.remove", data=removed_keys)

        if added_keys or updated_keys:
            emit_event(
                logger=logger,
                event="parameters.update",
                data={
                    key: new_parameter_metadata[key]
                    for key in set(added_keys) | set(updated_keys)
                },
            )

    @staticmethod
    @overload
    async def get_display_groups(
        *, deserialize: Literal[True] = True
    ) -> dict[str, dict[str, ParameterMetadata]]: ...

    @staticmethod
    @overload
    async def get_display_groups(
        *, deserialize: Literal[False] = False
    ) -> dict[str, str]: ...

    @staticmethod
    async def get_display_groups(
        *, deserialize: bool = True
    ) -> dict[str, str] | dict[str, dict[str, ParameterMetadata]]:
        if not is_valkey_available():
            raise ValkeyUnavailableError()

        async with AsyncValkeySession() as valkey:
            display_groups_serialized: dict[str, str] = await valkey.hgetall(
                "parameter_display_groups"
            )  # type: ignore

            if deserialize:
                return {
                    key: json.loads(value)
                    for key, value in display_groups_serialized.items()
                }
            return display_groups_serialized

    @staticmethod
    async def update_display_groups(
        *, new_display_groups: dict[str, Any], remove_unspecified: bool = True
    ) -> None:
        if not is_valkey_available():
            raise ValkeyUnavailableError()

        cached_display_groups_serialized = (
            await ParameterMetadataRepository.get_display_groups(deserialize=False)
        )

        new_display_groups_serialized = {
            key: json.dumps(value) for key, value in new_display_groups.items()
        }

        async with AsyncValkeySession() as valkey:
            await valkey.hset(
                "parameter_display_groups", mapping=new_display_groups_serialized
            )  # type: ignore

            added_keys, removed_keys, updated_keys = get_added_removed_and_updated_keys(
                new_display_groups,
                cached_display_groups_serialized,
            )

            if remove_unspecified and removed_keys:
                await valkey.hdel("parameter_display_groups", *removed_keys)  # type: ignore

        if removed_keys:
            emit_event(logger=logger, event="display_groups.remove", data=removed_keys)

        if added_keys or updated_keys:
            emit_event(
                logger=logger,
                event="display_groups.update",
                data={
                    key: new_display_groups[key]
                    for key in set(added_keys) | set(updated_keys)
                },
            )
