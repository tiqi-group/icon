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
