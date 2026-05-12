from __future__ import annotations

from typing import TYPE_CHECKING

from icon.client.api.experiments_controller import DisplayGroupProxy

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

    def __getitem__(self, display_group_name: str) -> DisplayGroupProxy:
        return DisplayGroupProxy(
            self._client,
            display_group_name,
            self._display_groups[display_group_name],
        )

    def __repr__(self) -> str:
        lines = ["<ParametersController>"]
        for group_name, params in self._display_groups.items():
            lines.append(f"  [{group_name}]")
            for meta in params.values():
                lines.append(f"    - {meta['display_name']}")
        return "\n".join(lines)
