from __future__ import annotations

from typing import TYPE_CHECKING

from icon.client.api.experiments_controller import (
    DisplayGroupProxy,
    get_display_group_identifier_dict,
)

if TYPE_CHECKING:
    from icon.client.client import Client


class ParametersController:
    """Client-side controller for global parameters.

    Wraps the server's ``parameters`` pydase service, providing access to all
    display groups and their parameters without going through a specific experiment.

    Usage::

        client = Client(url="ws://localhost:8001")
        client.parameters["Global Parameters"]["Tickle time"].value = 2.5
    """

    def __init__(self, client: Client) -> None:
        self._client = client
        self._display_groups: dict[str, dict] = client.trigger_method(
            "parameters.get_display_groups"
        )
        self._display_group_id_mapping = get_display_group_identifier_dict(
            list(self._display_groups.keys())
        )

    def __getitem__(self, display_group_name: str) -> DisplayGroupProxy:
        full_key = self._display_group_id_mapping.get(
            display_group_name, display_group_name
        )
        return DisplayGroupProxy(
            self._client,
            full_key,
            self._display_groups[full_key],
        )

    def __repr__(self) -> str:
        lines = ["<ParametersController>"]
        for short_name, full_key in self._display_group_id_mapping.items():
            lines.append(f"  [{short_name}]")
            for meta in self._display_groups[full_key].values():
                lines.append(f"    - {meta['display_name']}")
        return "\n".join(lines)
