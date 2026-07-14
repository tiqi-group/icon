"""Experiment data related structures."""

from dataclasses import dataclass
from typing import Literal, TypedDict

DatabaseValueType = bool | float | int | str


@dataclass
class Readouts:
    """Scalar/vector/shot readouts for a single data point."""

    result_channels: dict[str, float]
    """Mapping from result channel name to scalar value."""
    vector_channels: dict[str, list[float]]
    """Mapping from vector channel name to list of floats."""
    shot_channels: dict[str, list[int]]
    """Mapping from shot channel name to per-shot integers."""


@dataclass
class ExperimentDataPoint(Readouts):
    """A single data point with its context."""

    index: int
    """Sequential index of this data point."""
    scan_params: dict[str, DatabaseValueType]
    """Parameter values that produced this data point."""
    timestamp: str
    """Acquisition timestamp (ISO string)."""
    sequence_json: str
    """Serialized sequence JSON used for this data point."""


class PlotWindowMetadata(TypedDict):
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


class ReadoutMetadata(TypedDict):
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


class PlotWindows(TypedDict):
    """Grouping of plot window metadata by channel type."""

    result_channels: list[PlotWindowMetadata]
    """Plot window metadata for result channels."""
    shot_channels: list[PlotWindowMetadata]
    """Plot window metadata for shot channels."""
    vector_channels: list[PlotWindowMetadata]
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
class ParameterValue:
    timestamp: str
    value: DatabaseValueType


@dataclass
class ExperimentData:
    """Container for all experiment data returned to the API."""

    plot_windows: PlotWindows
    """Plot window metadata grouped by channel class."""
    shot_channels: dict[str, dict[int, list[int]]]
    """Shot channels as channel_name -> {index -> values}."""
    result_channels: dict[str, dict[int, float]]
    """Result channels as channel_name -> {index -> value}."""
    vector_channels: dict[str, dict[int, list[float]]]
    """Vector channels as channel_name -> {index -> values}."""
    scan_parameters: dict[str, dict[int, str | float]]
    """Scan parameters as param_id -> {index -> value/timestamp}."""
    json_sequences: list[list[int | str]]
    """List of [index, sequence_json] pairs (list for pydase JSON compatibility)."""
    realtime_scan: bool
    """True if the experiment has a realtime scan parameter."""
    parameters: dict[str, ParameterValue]
    """Mapping of parameter id to time series (tuple of timestamp str and value)."""
    total_data_points: int
    """Total number of data points in the HDF5 file (before truncation)."""
    fits: dict[str, dict[str, object]]
    """Fit results keyed by result channel name."""
