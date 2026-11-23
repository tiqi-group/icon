from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

from ionpulse_sequence_generator import (  # type: ignore
    Header,
    LinearSequence,
    System,
    Units,
)
from ionpulse_sequence_generator.hardware.readout import PlotWindowType

import pycrystal.database.local_cache
from pycrystal.parameters import Parameter
from pycrystal.readout import ReadoutMetadata

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pycrystal.device_parameters import DeviceParameters
    from pycrystal.utils.enums import ReadoutPostprocessingMethod

SEQUENCE_MAX_TIME_FIELD = "sequence_max_time_ns"
"""Sequence header field storing maximum sequence execution time."""


class DisplayGroup(Protocol):
    @staticmethod
    def display_name() -> str:
        """String used to display this group of parameters."""
        ...


class WaveformMetadata(TypedDict):
    index: int
    uid: int
    waveform_id: str
    n_samples: int


class ExperimentConfigDict(TypedDict):
    experiment_instances: list[tuple[type[Experiment], dict[str, Any]]]
    """List of tuples containing the experiment class and the kwargs passed for
    instantiation."""
    display_group_modules: set[str]
    """Set of module strings used to build the display groups. Every class containing
    parameters in this module will be displayed."""
    display_groups: set[type[DisplayGroup] | DeviceParameters]
    """Additional set of display groups. These are classes containing parameters,
    imported from other modules, or instances of DeviceParameters."""


class Experiment:
    """This is the base class for all experiments. It contains the basic functions that
    all experiments must implement.

    Attributes:
        _name (str): name of the experiment
        device_instr_mapping (dict[str, Callable[[], str]]): maps each device to a
            function generating the instructions. Devices in System map to the default
            pulse sequence.
        device_readout_mapping (dict[str, Callable[[], ReadoutMetadata]]): maps each
            device to a function generating the readout metadata. Devices with a readout
            channel in System map to the default readout metadata.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._check_subclassing_correctness()
        self._parameter_groups: dict[str, list[Parameter]] = {}
        self._sequence_header: Header
        self._sequence: LinearSequence | None = None
        self.define_parameters()

        self._waveform_metadata: dict[str, WaveformMetadata] = {}
        self.device_instr_mapping: dict[str, Callable[[], str]] = {}
        for k in System()._devices:
            self.device_instr_mapping[k] = self._pulse_sequence_str
        self.device_readout_mapping: dict[str, Callable[[], ReadoutMetadata]] = {}
        readout_hw = type(System().readout).__name__
        for ch in System()._idx_to_ch:
            if ch["hardware"] == readout_hw and ch["device"]:
                self.device_readout_mapping[ch["device"]] = ReadoutMetadata.from_system

    def _check_subclassing_correctness(self) -> None:
        """
        Checks that the pulse_sequence, define_parameters and define_output_traces
        functions have been overwritten by the child classes.

        Raises:
            NotImplementedError: If the functions have not been overwritten.
        """

        if type(self).pulse_sequence == Experiment.pulse_sequence:
            logger.error(
                "Experiment %s not overwriting _pulse_sequence", type(self).__name__
            )
            raise NotImplementedError(
                f"Please implement _pulse_sequence in {type(self).__name__}"
            )
        if type(self).define_output_traces == Experiment.define_output_traces:
            logger.error(
                "Experiment %s not overwriting _define_output_traces",
                type(self).__name__,
            )
            raise NotImplementedError(
                f"Please implement _define_output_traces in {type(self).__name__}"
            )

    def add_plot_windows(
        self,
        names: list[str],
        readout_channels: list[int],
        post_processing_methods: list[ReadoutPostprocessingMethod],
    ) -> None:
        """Adds a plot window to the experiment. The traces parameter is a dictionary
        containing the name of the trace and the "result channel" to use to generate the
        plot.

        Note: Deprecation Notice
            This method is deprecated. Use
            `System().readout.create_plot_window(window_name)` and
            `System().readout.create_readout_channel(channel_name, window_name, method)`
            from `ionpulse_sequence_generator`.

        Args:
            names: List of plot window names.
            readout_channels: List of integers specifying readout channel numbers.
            post_processing_methods: List of methods used to post-process the results.
                Gets mapped to the readout_channels.

        Example:
            The following call:
            ```python
            add_plot_windows(
                names=["Window 1", "Window 2", "Window 3"],
                readout_channels=[0,1,2],
                post_processing_methods=[
                    ReadoutPostprocessingMethod.AVERAGE,
                    ReadoutPostprocessingMethod.NONE,
                    ReadoutPostprocessingMethod.SUM
                ]
            )
            ```
            creates three shot channels plotted into separate windows each.
        """
        logger.warning(
            "add_plot_windows is deprecated. "
            "Instead use System().readout.create_plot_window(window_name) and"
            "System().readout.create_readout_channel(channel_name, window_name, method)"
            "from ionpulse sequence generator"
        )
        readout = System().readout
        for window_name in names:
            readout.create_plot_window(window_name)
        for i in range(len(names)):
            readout.create_readout_channel(
                names[i] + str(readout_channels[i]),
                readout.plot_windows[names[i]],
                post_processing_methods[i],
            )

    def add_histogram_window(self, name: str) -> None:
        """Adds a histogram window to the experiment. The shot_data is a dictionary
        containing the name of the histogram and the "shot channel" to use to generate
        the histogram.

        Note: Deprecation Notice
            This method is deprecated. Use `System().readout.create_shot_channel(name)`
            from `ionpulse_sequence_generator`.

        Args:
            name: Plot window name.
            channel_index: Index of the channel used to generate the histogram.
        """
        logger.warning(
            "add_histogram_window is deprecated. "
            "Instead use System().readout.create_shot_channel(name)"
            "from ionpulse sequence generator"
        )
        readout = System().readout
        histogram_plot_window = readout.plot_windows.get(
            "Histogram",
            readout.create_plot_window("Histogram", PlotWindowType.HISTOGRAM),
        )
        readout.create_shot_channel(name, histogram_plot_window)

    def _initialize_scan(
        self, n_shots: int | None = None, debug_level: int = logging.WARNING
    ) -> None:
        self._sequence_header = Header(debug_level)
        self._sequence = None
        if n_shots is not None:
            self._sequence_header.set_shots(n_shots)
        # reset output traces every time for now, until we can detect
        # which parameters changed in ICON
        self.clear_output_traces()
        self.define_output_traces()

    def define_parameters(self) -> None:
        """This is a function that any experiment can override to add local parameters.
        Here the user should define the parameters that will be used in the experiment.
        """

    def pulse_sequence(self) -> LinearSequence:
        """This is a virtual function that any experiment must re-write. Here the user
        should define the pulse sequence to be executed in the experiment. This function
        is called for every data point of the experiment. The function must update the
        sequence attribute of the experiment.

        Example:
            ```python
            def pulse_sequence(self) -> LinearSequence:
                self.sequence += do_something()
            ```
        """
        raise NotImplementedError("Please implement pulse_sequence in all experiments")

    def pulse_sequence_str_from_args(
        self,
        parameter_dict: dict[str, Any],
        n_shots: int,
        log_level: int = logging.ERROR,
    ) -> str:
        """Generate a JSON sequence for given parameters.

        Args:
            parameter_dict: Parameters values to use for the experiment.
            n_shots: Number of shots.

        Returns:
            JSON string containing the generated sequence.
        """
        warnings.warn(
            "`pulse_sequence_str_from_args()` is deprecated."
            "Use `pulse_sequence_from_args()` instead.",
            category=DeprecationWarning,
        )
        Parameter.db = pycrystal.database.local_cache.LocalCache(
            key_val_dict=parameter_dict,
        )

        self._initialize_scan(n_shots=n_shots, debug_level=log_level)
        return self._pulse_sequence_str()

    def _pulse_sequence_str(self) -> str:
        # use cached sequence for re-calls in multi-device
        # requires _initialize_scan to actually re-create the sequence
        if self._sequence is None:
            self._sequence = self.pulse_sequence()
            max_time_ns = float(self._sequence.get_time().value(Units.ns).max())
            self._sequence_header.add_field(SEQUENCE_MAX_TIME_FIELD, max_time_ns)
        return self._sequence.get_json_string(self._sequence_header)

    def pulse_sequence_from_args(
        self,
        parameter_dict: dict[str, Any],
        *,
        n_shots: int,
        device_id: str | None = None,
        log_level: int = logging.ERROR,
    ) -> dict[str, str] | str:
        """Generate a JSON sequence for given parameters.

        Args:
            parameter_dict: Parameters values to use for the experiment.
            n_shots: Number of shots.
            device_id: Device for which to generate a sequence. If `None`, a sequence
                is generated for every device in `device_instr_mapping`.

        Returns:
            JSON string containing the generated sequence, or a dict mapping each
            device name to its sequence if `device_id` is `None`.
        """
        Parameter.db = pycrystal.database.local_cache.LocalCache(
            key_val_dict=parameter_dict,
        )

        self._initialize_scan(n_shots=n_shots, debug_level=log_level)
        if device_id is None:
            return {k: v() for k, v in self.device_instr_mapping.items()}
        return self.device_instr_mapping[device_id]()

    def get_readout_metadata(
        self, parameter_dict: dict[str, Any], log_level: int = logging.ERROR
    ) -> ReadoutMetadata:
        """Fetch readout metadata for the experiment for the main device.

        Returns:
            Readout instance containing readout metadata for the experiment.
        """
        warnings.warn(
            "`get_readout_metadata()` is reprecated."
            "Use `get_readout_metadata_by_device()` instead.",
            category=DeprecationWarning,
        )
        Parameter.db = pycrystal.database.local_cache.LocalCache(
            key_val_dict=parameter_dict,
        )
        self._initialize_scan(debug_level=log_level)

        return ReadoutMetadata.from_system()

    def get_readout_metadata_per_device(
        self, parameter_dict: dict[str, Any], log_level: int = logging.ERROR
    ) -> list[tuple[str, ReadoutMetadata]]:
        """Fetch readout metadata for the experiment for each device.

        Returns:
            List of (device name, readout metadata) tuples, one for every device in
            `device_readout_mapping`.
        """
        Parameter.db = pycrystal.database.local_cache.LocalCache(
            key_val_dict=parameter_dict,
        )
        self._initialize_scan(debug_level=log_level)
        return [(k, v()) for k, v in self.device_readout_mapping.items()]

    def clear_output_traces(self) -> None:
        System().clear_readout()

    def define_output_traces(self) -> None:
        """This is a virtual function that any experiment must re-write. Here the user
        should define the output traces that will be shown in the experiment.

        The user can should use the Readout class from the ionpulse sequence generator
        to define plot windows and data channels used in the sequence, specifically:

        - PlotWindows
            Ionizer plot window to plot data into (used for Readout/Vector channels)
        - ShotChannels
            Store shot data (e.g. PMT readout for each shot)
        - ReadoutChannels
            Store experiment data and provide the option for postprocessing.
        - VectorChannels
            Store vector data from the experiment (e.g. timestamps)

        """
