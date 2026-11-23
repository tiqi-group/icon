"""This module contains useful utilities like a collection of enumerations
that can be passed to parameters to query values from a database.
"""

from enum import Enum

from ionpulse_sequence_generator import (  # type: ignore
    DiscriminatorType,
    ReadoutPostprocessingMethod,
)

__all__ = [
    "AOMPowers",
    "AOMTypes",
    "BeamOrientation",
    "BeamTypes",
    "CaIsotopes",
    "CaTransitions",
    "Detuning",
    "DiscriminatorType",
    "FrequencyTypes",
    "IonSpecies",
    "MotionalIdentifiers",
    "MotionalModes",
    "ParameterTypes",
    "PulseTypes",
    "ReadoutPostprocessingMethod",
]


class PulseTypes(Enum):
    """Useful pulse types."""

    DOPPLER_FAR = "far doppler cooling"
    DOPPLER_MID = "mid doppler cooling"
    DOPPLER_NEAR = "near doppler cooling"
    EIT = "EIT"
    SIGMA_SPIN_POL = "Sigma Spin Pol"
    PI = "Pi"
    PI_HALF = "Pi-half"
    MS = "MS"
    SDF = "SDF"
    DETECTION = "Detection"
    REPUMP = "Repump"
    CALIBRATION = "Cal"
    STANDARD = "Std"
    RSB = "rsb"
    BSB = "bsb"
    PAD = "Pad"
    SYSIPHUS = "Sysiphus"
    """Padding pulse; gets appended to doppler cooling, default cooling and
    spin polarisation to reset population to the ground state."""


class IonSpecies(Enum):
    """Ion species we can have in our experiments.

    This is currently not used."""

    CA40 = "Ca40"
    CA44 = "Ca44"
    BE = "Be"


class ParameterTypes(Enum):
    """Parameter types"""

    FREQUENCY = "frequency"
    AMPLITUDE = "amplitude"
    TIME = "time"
    PHASE = "phase"
    VOLTAGE = "voltage"
    BOOLEAN = "boolean"
    INT = "int"
    FLOAT = "float"
    ENUM = "enum"
    STRING = "string"


class FrequencyTypes(Enum):
    """Frequency parameter types."""

    OFFSET = "offset"
    STARKSHIFT = "stark shift"
    MOTIONAL = "motional"
    BARE = "bare"


class MotionalModes(Enum):
    """Motional modes directions of the ion on the trap."""

    AXIAL = "axial"
    RADIAL_1 = "radial 1"
    RADIAL_2 = "radial 2"


class MotionalIdentifiers(Enum):
    """Motional modes of the ion on the trap."""

    COM = "COM"
    STR = "STR"


class BeamTypes(Enum):
    """Collection of the lasers used in the labs."""

    BEAM_393 = "393"
    BEAM_397 = "397"
    BEAM_397_PI = "397p"
    BEAM_397_SIGMA = "397s"
    BEAM_866 = "866"
    BEAM_854 = "854"
    BEAM_850 = "850"
    BEAM_729 = "729"
    BEAM_423 = "423"
    BEAM_405 = "405"
    BEAM_733 = "733"
    BEAM_732 = "732"


class AOMTypes(Enum):
    """AOM types specifying how often the light passes through the AOM."""

    DP = "double-pass"
    SP = "single-pass"


class CaTransitions(Enum):
    """The Ca transitions between the S levels and the S and the D level."""

    SM12_TO_DM52 = "Sm1/2 to Dm5/2"
    SM12_TO_DM32 = "Sm1/2 to Dm3/2"
    SM12_TO_DM12 = "Sm1/2 to Dm1/2"
    SM12_TO_DP12 = "Sm1/2 to Dp1/2"
    SM12_TO_DP32 = "Sm1/2 to Dp3/2"
    SP12_TO_DM32 = "Sp1/2 to Dm3/2"
    SP12_TO_DM12 = "Sp1/2 to Dm1/2"
    SP12_TO_DP12 = "Sp1/2 to Dp1/2"
    SP12_TO_DP32 = "Sp1/2 to Dp3/2"
    SP12_TO_DP52 = "Sp1/2 to Dp5/2"
    SM12_TO_SP12 = "Sm1/2 to Sp1/2"


class BeTransitions(Enum):
    pass


class H2PTransitions(Enum):
    pass


class AOMPowers(Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"


class Detuning(Enum):
    CLOSE = "low"
    MID = "mid"
    FAR = "high"


class CaIsotopes(Enum):
    Ca40 = "Ca40"
    Ca42 = "Ca42"
    Ca43 = "Ca43"
    Ca44 = "Ca44"
    Ca46 = "Ca46"
    Ca48 = "Ca48"


class BeamOrientation(Enum):
    AXIAL = "axial"
    RADIAL = "radial"
