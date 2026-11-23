from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from ionpulse_sequence_generator import System as _System
from typing_extensions import Self


class PlotWindowType(Enum):
    """Type of the plot window."""

    NONE = auto()
    VECTOR = auto()
    HISTOGRAM = auto()
    READOUT = auto()


@dataclass
class PlotWindowMetadata:
    """Metadata describing a single plot window for visualization in the frontend.

    This metadata includes the plot's index within its type, the type of plot (e.g.,
    vector, histogram, or readout), and the list of channel names that are to be plotted
    in the respective window.
    """

    name: str
    """The name of the plot window"""
    index: int
    """The order of the plot window within its type (e.g., 0, 1, 2...)"""
    type: PlotWindowType
    """The type of the plot window"""
    channel_names: list[str]
    """A list of channel names to be plotted in this window"""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(type=PlotWindowType[raw.pop("type").upper()], **raw)


@dataclass
class ReadoutMetadata:
    """Metadata describing readout/shot/vector channels and their plot windows."""

    readout_channel_names: list[str]
    """A list of all readout channel names"""
    shot_channel_names: list[str]
    """A list of all shot channel names"""
    vector_channel_names: list[str]
    """A list of all vector channel names"""
    readout_channel_windows: list[PlotWindowMetadata]
    """List of `PlotWindowMetadata` of result channels"""
    shot_channel_windows: list[PlotWindowMetadata]
    """List of `PlotWindowMetadata` of shot channels"""
    vector_channel_windows: list[PlotWindowMetadata]
    """List of `PlotWindowMetadata` of vector channels"""

    @classmethod
    def from_system(cls) -> Self:
        readout = _System().readout.to_dict()

        windows: dict[str, Any] = {
            key: [PlotWindowMetadata.from_dict(win) for win in val]
            for key, val in readout.items()
            if key
            in {
                "readout_channel_windows",
                "shot_channel_windows",
                "vector_channel_windows",
            }
        }

        return cls(**{**readout, **windows})
