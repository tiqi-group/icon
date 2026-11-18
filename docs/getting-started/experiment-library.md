ICON interfaces with the **experiment library** to retrieve metadata about experiments and their parameters.


## Experiment library structure

The experiment library is a standalone Python project. A typical layout looks like this:

```bash
.
├── experiment_library
│   ├── experiments
│   │   ├── <your_experiment_1>.py
│   │   ├── ...
│   │   └── __init__.py
│   ├── frames                  # Optional: reusable experiment logic
│   │   ├── frame_cool_det.py
│   │   └── __init__.py
│   ├── globals
│   │   ├── global_functions.py
│   │   ├── global_parameters.py
│   │   └── __init__.py
│   ├── hardware_description
│   │   ├── hardware.py
│   │   └── __init__.py
│   └── __init__.py
└── pyproject.toml
```

The library uses **pycrystal** to define:

* the control hardware,
* global parameters,
* and experiment classes.

The most relevant modules for ICON are:

* `experiment_library.experiments` - experiment definitions.
* `experiment_library.globals` - global parameters and functions.

## Interaction with ICON

ICON uses [templates](https://github.com/tiqi-group/icon/tree/main/src/icon/server/data_access/templates) that are executed in the context of the experiment library. To do this, ICON:

1. Spawns a subprocess using the Python environment of the experiment library.
2. Fills the template values (parameter dictionary, and for experiment instances also the module name and instance name).
3. Executes the template to retrieve metadata about experiments and parameters.

This mechanism ensures ICON always uses the definitions and environment of the experiment library itself.

## Experiment class structure

Experiments are defined by subclassing `pycrystal.Experiment`. Local parameters (parameters scoped to an experiment instance) are created in `define_parameters`:

```python
# experiment_library/experiments/test_exp.py

from pycrystal import Experiment
from pycrystal.parameters import BooleanParameter


class TestExperiment(Experiment):
    def define_parameters(self) -> None:
        self.threshold = BooleanParameter(
            parameter_group="Local detection settings",
            description="Threshold",
            display_name_template="{description}",
        )
        self.detect_background = BooleanParameter(
            parameter_group="Local detection settings",
            description="Detect Background",
            display_name_template="{description}",
        )
```

This defines an experiment with two boolean parameters. Each parameter specifies:

* a **parameter group** (used for display grouping),
* a **description**,
* and a **display name template** (to control how the parameter is shown in the frontend).

## Experiment instances

To expose experiments to ICON, you define experiment instances in a `CONFIGURATION` dictionary inside the experiment module. This dictionary specifies which experiments should be available, how they are grouped, and which display groups are shown in the frontend:

```python
# experiment_library/experiments/test_exp.py

CONFIGURATION = {
    "display_groups": {
        Repumping,
        Detection,
    },
    "experiment_instances": [
        (TestExperiment, {"name": "Cool Det"}),
    ],
}
```

* `display_groups` - defines parameter groups to be shown in the experiment overview. These can include both experiment parameters and device parameters.
* `experiment_instances` - a list of tuples, each consisting of:
    * the experiment class,
    * and a dictionary of constructor arguments (e.g. `{"name": "Cool Det"}`).

This mechanism allows you to register multiple instances of the same experiment class (e.g. with different configurations) and control what parameter groups are visible in ICON.

## Post-processing (prototype)

An experiment can derive new channels from the readouts of each data point, for example a bright-state probability from the counts of each shot. ICON's post-processing worker calls the experiment's `post_processing` method for every data point before it stores and plots the data point.

This is a prototype: it needs no changes to pycrystal and no ICON import in the experiment library, and it will be replaced by a pycrystal API.

### Declare the derived channels

ICON only stores and plots channels the readout metadata declares. Declare the derived channels by overriding `get_readout_metadata_per_device`. Don't create them with `System().readout`: that would add them to the sequence, and the device would be asked for channels it cannot produce.

```python
import logging
from typing import Any

from pycrystal import Experiment
from pycrystal.readout import PlotWindowMetadata, PlotWindowType, ReadoutMetadata


class Detection(Experiment):
    ...

    def get_readout_metadata_per_device(
        self, parameter_dict: dict[str, Any], log_level: int = logging.ERROR
    ) -> list[tuple[str, ReadoutMetadata]]:
        metadata = super().get_readout_metadata_per_device(parameter_dict, log_level)
        # ICON plots the first device
        _, readout = metadata[0]
        readout.readout_channel_names.append("P(bright)")
        readout.readout_channel_windows.append(
            PlotWindowMetadata(
                name="Population",
                index=len(readout.readout_channel_windows),
                type=PlotWindowType.READOUT,
                channel_names=["P(bright)"],
            )
        )
        return metadata
```

A derived channel can also be added to the `channel_names` of an existing window instead of a new one.

### Write `post_processing`

ICON passes an object with the fields of the dataclasses below. Copy them into the experiment library for type hints and to test `post_processing` without ICON. `post_processing` may change the object it gets and return it, or return a new `ExperimentDataPoint` of the copied classes.

```python
from dataclasses import dataclass


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
    """Same fields as ICON's `icon.server.data_access.experiment_data.ExperimentDataPoint`."""

    index: int
    """Index of the data point in the scan."""
    scan_params: dict[str, bool | float | int | str]
    """Scanned parameter ID -> value."""
    timestamp: str
    """Acquisition time (ISO format)."""
    device_data: list[ExperimentDeviceDataPoint]
```

```python
from pycrystal.parameters import IntegerParameter


class Detection(Experiment):
    def define_parameters(self) -> None:
        self.bright_threshold = IntegerParameter(...)

    ...

    def post_processing(self, data: ExperimentDataPoint) -> ExperimentDataPoint:
        """Derive the channels declared in `get_readout_metadata_per_device`.

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
            d for d in data.device_data if "counts" in d.readouts.shot_channels
        )
        shots = device.readouts.shot_channels["counts"]
        threshold = self.bright_threshold().value()
        device.readouts.result_channels["P(bright)"] = sum(
            count > threshold for count in shots
        ) / len(shots)
        return data
```

Replace `counts` with the name of a shot channel of your experiment.
