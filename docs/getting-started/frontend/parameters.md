The parameters page in ICON displays the `pycrystal` parameters defined in the experiment library. In `pycrystal`, parameters represent values used when generating control sequences (e.g., frequencies, durations, amplitudes). They act as interfaces to the InfluxDB database.

## How Parameters are Displayed

How a parameter is displayed is defined through its **namespace**, **display group** and **display name**, i.e. each parameter will be displayed with its display name within its namespace, grouped under the display group.

The **namespace** is defined by the python module where it is defined (e.g. `experiment_library.globals.global_parameters`) and optionally the experiment class and instance name when the parameter is defined within the `define_parameters` method of an `Experiment` class (e.g. `experiment_library.experiments.exp_cool_det.ExperimentCoolDet (Cool Det)`, where the class name is appended to the module name, and the instance name is within parentheses).

The **display group** is defined by the `display_group` passed to the parameter. The parameters will be organized under this display group in the frontend. If it is not set manually, the display group is calculated as follows:

- when the parameter is defined within the `define_parameters` method of an experiment class, the display group defaults to `"Local Parameters"`

    !!! example

        The display group of the following parameter is `"Local Parameters"`:

        ```python
        from pycrystal.experiment import Experiment

        class TestExperiment(Experiment):
            # ...
            def define_parameters(self) -> None
                self.my_frequency = FrequencyParameter()
        ```

- when the parameter is defined as an attribute of a wrapper class that has defined a static-/class-method called `display_name`, the string returned from that method will be used. Otherwise, the name of the containing class is taken as the display group.

    !!! example

        The display group of the following parameter is `"My display group"`:

        ```python
        class MyDisplayGroup:
            my_frequency = FrequencyParameter()

            @staticmethod
            def display_group() -> str:
                return "My display group"
        ```

The **display name** is defined by the `display_name_template` that is passed to the parameter constructor. It is a template string used to define a custom display name format for each parameter combination. The template allows placeholders that will be dynamically filled based on the provided parameters and other class attributes. It defaults to `"{specifiers}"`.

The following placeholders can be used:

- `{namespace}`: The namespace associated with the parameter which is generated
  from the module name and the experiment instance name of parameters defined
  within an experiment's `define_parameters` method.
- `{parameter_group}`: The name of the parameter group, which corresponds to a
  field in the InfluxDB parameter backend.
- `{specifiers}`: A summary of all parameter specifiers (tags in InfluxDB)
  generated from `kwargs`, formatted as `EnumClass.EnumMember.value`. This
  placeholder provides a full list of specifiers for a comprehensive display
  name.
- `{specifiers_full}`: A summary of all parameter specifiers (tags in InfluxDB)
  generated from `kwargs`, formatted as `key=EnumClass.EnumMember.value`. This
  placeholder provides a full list of specifiers for a comprehensive display
  name.
- Additional `{key}` placeholders: Each `kwargs` key can also be used as a 
  placeholder to display specific parameter values. For example, `{mode}` would
  refer to the value of `mode` if it is a key in `kwargs`.

!!! example

    To generate display names with the format `"experiment_library.globals.global_parameters: default - mode=MotionalModes.AXIAL"`, use:

    ```python
    display_name_template = "{namespace}: {parameter_group} - mode={mode}"
    ```
