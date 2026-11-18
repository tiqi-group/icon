# Code of the experiment library: its imports and aliases follow the library's style
# ruff: noqa: I001, N813
"""Example experiment deriving a channel in ICON's post-processing (prototype).

The device returns the PMT counts of every shot in the shot channel "counts". The
result channel "thresholded_counts", the fraction of shots with more counts than the
experiment's threshold, is not computed on the device but in `post_processing`, which
ICON calls for every data point before storing and plotting it.
"""

import logging
from dataclasses import dataclass
from typing import Any

from ionpulse_sequence_generator import LinearSequence, System
from ionpulse_sequence_generator.hardware.readout import PlotWindowType
from pycrystal import Experiment
from pycrystal.parameters import IntegerParameter
from pycrystal.readout import PlotWindowMetadata, ReadoutMetadata
from pycrystal.readout import PlotWindowType as MetadataPlotWindowType
from pycrystal.utils import PulseTypes

from experiment_library.globals.cooling import doppler_cooling
from experiment_library.globals.global_parameters import Detection, Repumping
from experiment_library.globals.global_parameters import Globals as gl
from experiment_library.hardware_description.hardware import hardware
from experiment_library.utils.enums import Beam397, BeamTypes

SHOT_CHANNEL = "counts"
"""Counts of every shot, returned by the device."""
DERIVED_CHANNEL = "thresholded_counts"
"""Fraction of shots above the threshold, derived in `post_processing`."""


# Same fields as ICON's `ExperimentDataPoint`, which ICON passes to `post_processing`.
# Only needed for type hints and to test `post_processing` without ICON.
@dataclass
class Readouts:
    """Readouts of one device for one data point, keyed by channel name."""

    result_channels: dict[str, float]
    vector_channels: dict[str, list[float]]
    shot_channels: dict[str, list[int]]
    """One value per shot."""


@dataclass
class ExperimentDeviceDataPoint:
    device_id: str
    readouts: Readouts
    hardware_instructions: str
    """The sequence the device ran."""


@dataclass
class ExperimentDataPoint:
    index: int
    """Index of the data point in the scan."""
    scan_params: dict[str, bool | float | int | str]
    """Scanned parameter ID -> value."""
    timestamp: str
    """Acquisition time (ISO format)."""
    device_data: list[ExperimentDeviceDataPoint]


class PostProcessingExample(Experiment):
    def define_parameters(self) -> None:
        self.threshold = IntegerParameter(
            default_value=3,
            parameter_group="Local detection settings",
            name="threshold",
            display_name_template="{name}",
            display_group="Local detection settings",
        )

    def define_output_traces(self) -> None:
        # Only the channels the device fills. The derived channel must not be created
        # here, else the device would be asked for it.
        readout = System().readout
        histogram_window = readout.create_plot_window(
            name="Histogram (Counts)", plot_window_type=PlotWindowType.HISTOGRAM
        )
        readout.create_shot_channel(name=SHOT_CHANNEL, plot=histogram_window)

    def get_readout_metadata_per_device(
        self, parameter_dict: dict[str, Any], log_level: int = logging.ERROR
    ) -> list[tuple[str, ReadoutMetadata]]:
        # Declares the derived channel to ICON only: the sequence never sees it.
        metadata = super().get_readout_metadata_per_device(parameter_dict, log_level)
        # ICON plots the first device
        _, readout = metadata[0]
        readout.readout_channel_names.append(DERIVED_CHANNEL)
        readout.readout_channel_windows.append(
            PlotWindowMetadata(
                name="Thresholded Counts",
                index=len(readout.readout_channel_windows),
                type=MetadataPlotWindowType.READOUT,
                channel_names=[DERIVED_CHANNEL],
            )
        )
        return metadata

    def pulse_sequence(self) -> LinearSequence:
        seq = LinearSequence("Post-processing example")
        seq += doppler_cooling(PulseTypes.DOPPLER_FAR, False)  # noqa: FBT003
        seq += doppler_cooling(PulseTypes.DOPPLER_MID, False)  # noqa: FBT003
        seq.sync()
        seq += self.detection()
        seq.sync()
        return seq

    def detection(self) -> LinearSequence:
        readout = System().readout
        seq = LinearSequence("detection")
        detection_time = gl.detection.time()
        seq += hardware.rfs[BeamTypes.BEAM_397_PI, Beam397.PCF].request_pulse(
            frequency=gl.detection.frequency(beam_type=Beam397.PCF),
            amplitude=gl.detection.amplitude(beam_type=Beam397.PCF),
            pulse_duration=detection_time,
        )
        seq += hardware.rfs[BeamTypes.BEAM_866].request_pulse(
            frequency=gl.repumping.frequency(beam_type=BeamTypes.BEAM_866),
            amplitude=gl.repumping.amplitude(beam_type=BeamTypes.BEAM_866),
            pulse_duration=detection_time,
        )
        # No discriminator: the device only returns the counts of every shot
        seq += hardware["pmt"].request_detection(
            shot_channel=readout.shot_channels[SHOT_CHANNEL],
            name="counts",
            time=detection_time,
        )
        seq.sync()
        return seq

    def post_processing(self, data: ExperimentDataPoint) -> ExperimentDataPoint:
        """Derive "thresholded_counts" from the counts of this data point's shots.

        Prototype limitations:
        - Called once per data point, on a new experiment instance: nothing stored on
          `self` carries over to the next data point.
        - Not called for data points that failed on a device.
        - Parameters (`self.<param>()`) hold the values this data point's sequence was
          generated with. They are read-only: changes are not stored.
        - Raw channels are read-only: only channels the devices did not return are kept.
        - Every new result channel must be declared, else the job run fails. Declared
          channels left unset, or all of them if this raises, are stored as NaN: the
          first error is logged to the job run, which goes on.
        - Shot channels need one value per shot. Vector channels are stored, not plotted.
        - Runs in the experiment library's environment and must return within 60 s.
        """
        device = next(
            d for d in data.device_data if SHOT_CHANNEL in d.readouts.shot_channels
        )
        counts = device.readouts.shot_channels[SHOT_CHANNEL]
        threshold = self.threshold().value()
        device.readouts.result_channels[DERIVED_CHANNEL] = sum(
            count > threshold for count in counts
        ) / len(counts)
        return data


CONFIGURATION = {
    "display_groups": {
        Repumping,
        Detection,
    },
    "experiment_instances": [
        (PostProcessingExample, {"name": "PostProcessingExample"}),
    ],
}
