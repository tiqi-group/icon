"""Experiment data related structures."""

import base64
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from typing import Self

DatabaseValueType = bool | float | int | str


@dataclass
class Readouts:
    """Scalar/vector/shot readouts for a single data point from one device."""

    result_channels: dict[str, float]
    """Mapping from result channel name to scalar value."""
    vector_channels: dict[str, list[float]]
    """Mapping from vector channel name to list of floats."""
    shot_channels: dict[str, list[int]]
    """Mapping from shot channel name to per-shot integers."""


@dataclass
class ReadoutSequences:
    """Scalar/vector/shot readouts for multiple single data points from one device."""

    result_channels: dict[str, dict[int, float]] = field(default_factory=dict)
    """Result channels as channel_name -> {index -> value}."""
    vector_channels: dict[str, dict[int, list[float]]] = field(default_factory=dict)
    """Vector channels as channel_name -> {index -> values}."""
    shot_channels: dict[str, dict[int, list[int]]] = field(default_factory=dict)
    """Shot channels as channel_name -> {index -> values}."""


@dataclass
class ExperimentDeviceDataPoint:
    """Device specific data for a single data point."""

    device_id: str
    """ID of the device this data is from / for."""
    readouts: Readouts
    """Readouts from the device."""
    hardware_instructions: bytes
    """Serialized hardware instructions used for this data point."""


@dataclass
class ExperimentDataPoint:
    """A single data point with its context."""

    index: int
    """Sequential index of this data point."""
    scan_params: dict[str, DatabaseValueType]
    """Parameter values that produced this data point."""
    timestamp: str
    """Acquisition timestamp (ISO string)."""
    device_data: list[ExperimentDeviceDataPoint]
    """Readouts and hardware instructions per device."""

    def serialize(self) -> dict[str, Any]:
        """Serialize bytes in hardware instructions to base64 encoded string."""
        d = asdict(self)
        return {
            "device_data": [
                {
                    "hardware_instructions": base64.b64encode(
                        p.pop("hardware_instructions")
                    ).decode("utf-8"),
                    **p,
                }
                for p in d.pop("device_data")
            ],
            **d,
        }


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
    type: Literal["vector", "histogram", "readout"]
    """The type of the plot window"""
    channel_names: list[str]
    """A list of channel names to be plotted in this window"""


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
    def from_dict(cls, data: dict[str, Any]) -> "Self":
        return cls(
            readout_channel_windows=[
                PlotWindowMetadata(**d) for d in data.pop("readout_channel_windows")
            ],
            shot_channel_windows=[
                PlotWindowMetadata(**d) for d in data.pop("shot_channel_windows")
            ],
            vector_channel_windows=[
                PlotWindowMetadata(**d) for d in data.pop("vector_channel_windows")
            ],
            **data,
        )


@dataclass
class PlotWindows:
    """Grouping of plot window metadata by channel type."""

    result_channels: list[PlotWindowMetadata] = field(default_factory=list)
    """Plot window metadata for result channels."""
    shot_channels: list[PlotWindowMetadata] = field(default_factory=list)
    """Plot window metadata for shot channels."""
    vector_channels: list[PlotWindowMetadata] = field(default_factory=list)
    """Plot window metadata for vector channels."""


@dataclass
class FitResult:
    """Result of a curve fit operation."""

    result_channel: str
    func_type: str
    x_range: list[float] | None
    init: dict[str, float]
    result: dict[str, float]
    goodness: dict[str, float]
    success: bool
    message: str
    fit_curve: dict[str, list[float]] | None = None


@dataclass
class ExperimentDeviceData:
    """Device specific data for multiple data points."""

    device_id: str
    """ID of the device this data is from / for."""
    readouts: ReadoutSequences = field(default_factory=ReadoutSequences)
    """Readouts from the device."""
    hardware_instructions: list[tuple[int, bytes]] = field(default_factory=list)
    """Serialized hardware instructions used for this data point."""
    plot_windows: PlotWindows = field(default_factory=PlotWindows)
    """Plot window metadata grouped by channel class."""
    fits: dict[str, FitResult] = field(default_factory=dict)
    """Fit results keyed by result channel name."""


@dataclass
class ParameterValue:
    timestamp: str
    value: DatabaseValueType


@dataclass
class ExperimentData:
    """Container for all experiment data returned to the API."""

    device_data: list[ExperimentDeviceData] = field(default_factory=list)
    """Device specific data for multiple datapoints."""
    scan_parameters: dict[str, dict[int, str | float]] = field(default_factory=dict)
    """Scan parameters as param_id -> {index -> value/timestamp}."""
    realtime_scan: bool = False
    """True if the experiment has a realtime scan parameter."""
    parameters: dict[str, ParameterValue] = field(default_factory=dict)
    """Mapping of parameter id to time series (tuple of timestamp str and value)."""
    total_data_points: int = 0
    """Total number of data points in the HDF5 file (before truncation)."""

    def serialize(self) -> dict[str, Any]:
        """Serialize bytes in hardware instructions to base64 encoded string."""
        d = asdict(self)
        return {
            "device_data": [
                {
                    "hardware_instructions": base64.b64encode(
                        p.pop("hardware_instructions")
                    ).decode("utf-8"),
                    **p,
                }
                for p in d.pop("device_data")
            ],
            **d,
        }
