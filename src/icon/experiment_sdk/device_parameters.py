class DeviceParameters:
    """Helper class to include parameters from a pydase device in the experiment display
    groups.

    Instances of this class can be added to the `display_groups` set in an experiment's
    CONFIGURATION. The provided `device_name` must match the name of a device defined in
    icon. All parameters from that device will then be available in the experiment
    instance overview and job view.

    This class does not provide any additional functionality beyond serving as a marker
    for icon to include device parameters.

    Example:
        Add an instance of the `DeviceParameters` class to the "display_groups" set of
        the experiment configuration to display it in the experiment page:

        ```python
        # experiment_library/experiments/<some_experiment>.py
        CONFIGURATION = {
            "display_groups": {
                DeviceParameters(device_name="my pydase service"),
            },
            "experiment_instances": [
                # ...
            ],
        }
        ```
    """

    def __init__(self, device_name: str) -> None:
        self.device_name = device_name
