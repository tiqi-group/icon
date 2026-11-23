"""
This module contains classes that provide an interface to query and set values in a
database.
The class instances (from now on called `parameters`) interface with a database that is
set by the user and are designed to be reusable, i.e. to parameterise multiple variables
with the same physical meaning.

For more information, see [here](../user-guide/parameters.md).
"""

from __future__ import annotations

import itertools
import logging
import sys
import warnings
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, final

from ionpulse_sequence_generator import Units  # type: ignore
from ionpulse_sequence_generator.parameter.parameter import (  # type: ignore
    Amp,
    Freq,
    Phase,
    Time,
)
from ionpulse_sequence_generator.parameter.parameter import (
    Parameter as ISG_Parameter,
)

from pycrystal.database.database import (
    Database,
    DatabaseValueType,
    DummyDB,
)
from pycrystal.parameter_registry import ParameterMetadata, ParameterRegistry
from pycrystal.utils import FrequencyTypes, ParameterTypes, reissue_warnings
from pycrystal.utils.defaults import DefaultUnitConfiguration
from pycrystal.utils.format import format_parameter
from pycrystal.utils.helpers import (
    find_caller_module,
)
from pycrystal.utils.parameter_id_utils import get_parameter_identifier_from_specifiers

if TYPE_CHECKING:
    from ionpulse_sequence_generator.hardware.units import Unit  # type: ignore

    import pycrystal.experiment

logger = logging.getLogger(__name__)
default_units = DefaultUnitConfiguration()

__all__ = [
    "AmplitudeParameter",
    "BareCarrierFrequency",
    "FrequencyOffset",
    "FrequencyParameter",
    "MotionalFrequency",
    "Parameter",
    "PhaseParameter",
    "StarkShiftFrequency",
    "StringParameter",
    "TimeParameter",
]

NAMESPACE_TEMPLATE = "{module_name}.{containing_experiment_instance_name}"
DISPLAY_GROUP_TEMPLATE = "{local_parameters_or_containing_class}"

DEFAULT_PARAMETER_GROUP = "default"
DEFAULT_DISPLAY_NAME_TEMPLATE = "{param_type} {specifiers}"

ParameterValueTypes = float | bool | int | str | Enum


class Parameter(ABC):
    """ABC abstracting the way parameters are queried from a database."""

    registry = ParameterRegistry()
    """Registers the parameter identifiers grouped by their containing module and
    display groups. The "all" key contains all the parameter identifiers.
    """

    db: ClassVar[Database] = DummyDB()
    """Class variable used to retrieve from and set parameters in a database used by
    specific experiments. It defaults to :class:`DummyDB` which generates random numbers
    and should be set to an actual database implementing the methods ``query`` and
    ``update``."""

    @abstractmethod
    def __init__(
        self,
        *,
        param_type: ParameterTypes,
        default_value: ParameterValueTypes,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        units: Unit = Units.none,
        min_value: float | None = None,
        max_value: float | None = None,
        read_only: bool = False,
        allowed_values: list[Any] | None = None,
        **kwargs: list[Enum | str] | Enum | str,
    ) -> None:
        """Init

        Args:
            default_value: default value of the parameter set. each parameter class has
                a default value, but you can overwrite it by passing in another value.
            parameter_group: field in InfluxDB. Used to separate parameters into
                different groups. Defaults to `"default"`.

                !!! note

                    If you do not set this specifier, you are in danger of defining
                    multiple parameters with the same parameter ids:
                    ```python
                    # those two parameters access the **same** database value!
                    frequency = FrequencyParameter(
                        pulse_type=[PulseTypes.DOPPLER_FAR, PulseTypes.DOPPLER_MID]
                    )
                    other_frequency = FrequencyParameter(
                        pulse_type=[PulseTypes.DOPPLER_FAR, PulseTypes.DOPPLER_MID]
                    )
                    ```

            display_name_template: template string used to define a custom display name
                format for each parameter combination. The template allows placeholders
                that will be dynamically filled based on the provided parameters and
                other class attributes. Defaults to `"{specifiers}"`.

                Available placeholders:

                - `{namespace}`: The namespace associated with the parameter which is
                    generated from the module name and the experiment instance name of
                    parameters defined within an experiment's `define_parameters`
                    method.
                - `{parameter_group}`: The name of the parameter group, which
                    corresponds to a field in the InfluxDB parameter backend.
                - `{specifiers}`: A summary of all parameter specifiers (tags in
                    InfluxDB) generated from `kwargs`, formatted as
                    `EnumClass.EnumMember.value`. This placeholder provides a full list
                    of specifiers for a comprehensive display name.
                - `{specifiers_full}`: A summary of all parameter specifiers (tags in
                    InfluxDB) generated from `kwargs`, formatted as
                    `key=EnumClass.EnumMember.value`. This placeholder provides a full
                    list of specifiers for a comprehensive display name.
                - Additional `{key}` placeholders: Each `kwargs` key can also be used as
                    a placeholder to display specific parameter values. For example,
                    `{mode}` would refer to the value of `mode` if it is a key in
                    `kwargs`.

                !!! example

                    To generate display names with the format
                    "globals: default - mode=MotionalModes.AXIAL", use:

                    ```python
                    display_name_template = "{namespace}: {parameter_group} - mode={mode}"
                    ```

            display_group: optional display group within the namespace. If provided,
                parameters will also be organized under this display group in the
                frontend. If it is not set manually, the display group is calculated as
                follows:

                - when the parameter is defined within the `define_parameters` method of
                    an experiment class, the display group defaults to
                    `"Local Parameters"`

                    !!! example

                        The display group of the following parameter is
                        `"Local Parameters"`:

                        ```python
                        from pycrystal.experiment import Experiment

                        class TestExperiment(Experiment):
                            # ...
                            def define_parameters(self) -> None
                                self.my_frequency = FrequencyParameter()
                        ```

                - when the parameter is defined as an attribute of a wrapper class that
                    has defined a static-/class-method called `display_name`, the string
                    returned from that method will be used. Otherwise, the name of the
                    containing class is taken as the display group.

                    !!! example

                        The display group of the following parameter is
                        `"My display group"`:

                        ```python
                        class MyDisplayGroup:
                            my_frequency = FrequencyParameter()

                            @staticmethod
                            def display_group() -> str:
                                return "My display group"
                        ```


            units: The unit associated with the parameter, used for display purposes in
                the frontend.

            units: the unit associated with the parameter, used for display purposes in
                the frontend and conversion in the backend. The value is an instance of
                the `Units` enumeration and defaults to `Units.NONE` if not specified.
            min_value: minimum value a number parameter can take (e.g. amplitudes are
                between 0 and 100)
            max_value: maximum value a number parameter can take (e.g. amplitudes are
                between 0 and 100)
            allowed_values: List of values defining the allowed parameter values. This
                is currently only supported by the ComboBoxParameter.

        Example:
            You can initialise your database in your experiment setup file like so:

            ```python
            from pycrystal.parameters import Parameter
            from pycrystal.database import <database>

            Parameter.db = <database>
            ```

            For more information, see the
            [databases documentation](../user-guide/databases.md).
        """  # noqa: E501

        self._parameter_group = parameter_group
        self._units = units
        self._default_value = default_value
        self._min_value = min_value
        self._max_value = max_value
        self.read_only = read_only
        self._display_name_template = display_name_template
        self._kwargs = kwargs
        self._param_type = param_type
        self._display_group = display_group
        self._allowed_values = allowed_values
        self._set_namespace_and_display_group()

        self._fixed_specifiers: dict[str, Enum | str] = {
            "namespace": self._namespace,
            "parameter_group": self._parameter_group,
            "param_type": self._param_type,
        }
        self._dynamic_specifiers: dict[str, list[Enum | str]] = {}
        self._split_into_fixed_and_dynamic_specifiers(self._kwargs)

        if "prefix" in self._kwargs:
            warnings.warn(
                "`prefix` does not have any effect any more. "
                "Please use `display_name_template`."
            )

        # add parameter to registry
        self.registry.add_parameters(
            parameter_dict=self._parameters,
            namespace=self._namespace,
            display_group=self._display_group,
        )

    def __set_name__(self, owner: type, name: str) -> None:
        """Setting the parameter as class attribute, this method will add the parameter
        to a display group named as the class name or, if available, its display_name()
        return value."""

        group_name = self._display_group

        if self._display_group is None:
            try:
                # When the parameter class has defined a static-/class-method called
                # display_name, use the result for displaying the group on clients
                class_display_name = owner.display_name()  # type: ignore
            except AttributeError:
                class_display_name = owner.__name__
            group_name = DISPLAY_GROUP_TEMPLATE.format(
                local_parameters_or_containing_class=class_display_name
            )

        self.registry.add_parameters(
            parameter_dict=self._parameters,
            namespace=self._namespace,
            display_group=group_name,
        )

    def _set_namespace_and_display_group(self) -> None:
        caller_module_name, caller_frame_depth = find_caller_module()

        containing_experiment_instance = (
            self._get_containing_experiment_instance_from_frame_depth(
                frame_depth=caller_frame_depth
            )
        )
        if containing_experiment_instance is not None:
            caller_module_name = (
                f"{containing_experiment_instance.__module__}."
                f"{type(containing_experiment_instance).__name__}"
            )

            if self._display_group is None:
                self._display_group = DISPLAY_GROUP_TEMPLATE.format(
                    local_parameters_or_containing_class="Local Parameters"
                )

        self._namespace = NAMESPACE_TEMPLATE.format(
            module_name=caller_module_name,
            containing_experiment_instance_name=containing_experiment_instance._name
            if containing_experiment_instance is not None
            else ".",
        ).strip(".")

    def _get_containing_experiment_instance_from_frame_depth(
        self, frame_depth: int | None = None
    ) -> pycrystal.experiment.Experiment | None:
        """Gets class instance containing the parameter reference, given the stack frame
        depth."""

        import pycrystal.experiment

        if frame_depth is None:
            _, frame_depth = find_caller_module()

        frame = sys._getframe(frame_depth)
        caller_locals = frame.f_locals
        for var_name, var_value in caller_locals.items():
            if var_name == "self" and isinstance(
                var_value, pycrystal.experiment.Experiment
            ):
                return var_value
        return None

    @property
    def _parameters(self) -> dict[str, ParameterMetadata]:
        parameter_dict: dict[str, ParameterMetadata] = {}

        # Generate all combinations of Enum values
        enum_combinations = itertools.product(
            *[
                value
                if isinstance(value, list)  # If it's a list of Enum instances
                else [value]  # If it's a single Enum instance
                for value in self._kwargs.values()
            ]
        )

        def normalise_allowed_values(
            allowed_values: list[Any] | None,
        ) -> list[str] | None:
            """Converts entries of allowed_values list into a list of strings or returns
            None."""

            if allowed_values is None:
                return None
            return [
                value.value if isinstance(value, Enum) else value
                for value in allowed_values
            ]

        for combo in enum_combinations:
            parameter_str = get_parameter_identifier_from_specifiers(
                namespace=self.namespace,
                parameter_group=self.parameter_group,
                param_type=self._param_type,
                **dict(zip(self._kwargs.keys(), combo)),
            )

            parameter_dict[parameter_str.strip()] = {
                "display_name": self._get_display_name_from_specifiers(
                    **dict(zip(self._kwargs.keys(), combo))
                ),
                "unit": self.units.name,
                "default_value": self._default_value.value
                if isinstance(self._default_value, Enum)
                else self._default_value,
                "min_value": self._min_value,
                "max_value": self._max_value,
                "allowed_values": normalise_allowed_values(self._allowed_values),
                "read_only": self.read_only,
            }

        return parameter_dict

    def _get_display_name_from_specifiers(self, **kwargs: Enum | str) -> str:
        """Prepare the display name based on the template and combination of
        parameters."""

        kwargs.update(
            {
                "namespace": self._namespace,
                "parameter_group": self._parameter_group,
                "param_type": self._param_type.value,
                "specifiers_full": " - ".join(
                    f"{key}={value.value}"
                    if isinstance(value, Enum)
                    else f"{key}={value}"
                    for key, value in kwargs.items()
                    if key not in {"namespace", "parameter_group"}
                ),
                "specifiers": " - ".join(
                    f"{value.value}" if isinstance(value, Enum) else f"{value}"
                    for key, value in kwargs.items()
                    if key not in {"namespace", "parameter_group"}
                ),
            }
        )
        return self._display_name_template.format(**kwargs).strip()

    def _split_into_fixed_and_dynamic_specifiers(
        self, specifiers: dict[str, Enum | list[Enum | str] | str]
    ) -> None:
        """Helper function which splits the specifiers into fixed specifiers and dynamic
        specifiers.

        Dynamic specifiers need to be provided in the call while fixed
        specifiers cannot be changed when getting or setting a value through the
        Parameter instance.

        Args:
            specifiers: A dictionary containing the specifiers for the parameter. Values
                of the dictionary can be either an Enum for a fixed specifier or a list
                of Enums for a variable specifier.
        """

        for key, value in specifiers.items():
            if isinstance(value, list) and all(
                isinstance(v, Enum | str) for v in value
            ):
                self._dynamic_specifiers[key] = value
            elif isinstance(value, Enum | str):
                self._fixed_specifiers[key] = value
            else:
                raise TypeError(
                    f"Argument '{key}' must be an Enum or a str, or a list of Enum or "
                    f"str, got {type(value).__name__} instead."
                )

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def parameter_group(self) -> str:
        return self._parameter_group

    @property
    def fixed_specifiers(self) -> dict[str, Enum | str]:
        return self._fixed_specifiers

    @property
    def dynamic_specifiers(self) -> dict[str, list[Enum | str]]:
        return self._dynamic_specifiers

    @property
    def units(self) -> Unit:
        """The unit of the parameter.

        Returns:
            Unit of the parameter.
        """

        return self._units

    def __call__(self, **kwargs: Any) -> ISG_Parameter:
        """Retrieve the value of the parameter specified by ``**kwargs`` after
        performing some checks."""

        kwargs = self._check_and_update_request_args(**kwargs)

        result = self.retrieve_parameter(**kwargs)

        return self._post_process(database_value=result)

    @reissue_warnings(3)  # type: ignore
    @final
    def retrieve_parameter(
        self,
        **kwargs: Any,
    ) -> DatabaseValueType:
        """Queries value from database using kwargs and instance attributes.

        Queries the database with the items given in ``self._fixed_specifiers`` and
        kwargs without overwriting existing items in kwargs. Values defined by
        the class (e.g. param_type or frequency_type) are not changed.
        When 'name' was provided as a kwarg at instantiation it will be used to
        directly query the database.

        Args:
            kwargs: dictionary containing key, value pairs used to query the database.

        Returns:
            Value retrieved from the database.
        """

        query_result = self.db.query(**kwargs)

        if query_result is None:
            logger.error(
                "Can't get any value for the parameter %s", format_parameter(**kwargs)
            )
            raise ValueError(
                f"Parameter {kwargs} not found in parameter Cache. Please check that "
                "the parameter has been initialised"
            )
        return query_result

    @reissue_warnings(2)  # type: ignore
    @final
    def set_value(
        self,
        new_value: float,
        **kwargs: Any,
    ) -> None:
        """Sets value in database using kwargs and instance attributes.

        Queries the database with the items given in self._fixed_specifiers and kwargs
        without overwriting existing items in kwargs. Values defined by the class (e.g.
        param_type or frequency_type) are not changed.

        When 'name' was provided as a kwarg at instantiation it will be used to directly
        query the database.

        Prints warnings and raises exceptions as defined in `_update_request_args`.
        """

        # checks:
        # Min max value, other posible values defined by used.
        self._value_check(new_value)

        # checking kwargs and adding items from self._fixed_specifiers
        kwargs = self._check_and_update_request_args(**kwargs)

        # set parameter to `new_value` via the db
        self.db.update(
            new_value=new_value,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> ISG_Parameter:
        """Apply any necessary transformations to the value retrieved from the
        database."""

        raise NotImplementedError

    @abstractmethod
    def _value_check(self, new_value: float) -> None:
        """Checks if value to be passed to the parameter is valid."""

        raise NotImplementedError

    @final
    def _check_and_update_request_args(self, **kwargs: Any) -> dict[str, Any]:
        """Checking validity of kwargs and adding items from self._fixed_specifiers
        without overwriting any existing items in kwargs.

        This methods ensure that all dynamic keyword arguments have benn specified and
        no additional kwargs have been added.
        """

        self.__ensure_fixed_kwargs_stay_unchanged(**kwargs)
        self.__ensure_dynamic_kwargs_where_specified(**kwargs)
        self.__ensure_no_additional_kwargs_where_specified(**kwargs)

        # adding items from self._fixed_specifiers to kwargs without overwriting
        # any existing items in kwargs
        return self._fixed_specifiers | kwargs

    def __ensure_fixed_kwargs_stay_unchanged(self, **kwargs: Any) -> None:
        for key in self._fixed_specifiers:
            if key in kwargs:
                logger.debug(
                    "Attribute '%s' was already initialised but is supplied as "
                    "kwarg. Ignoring passed value...",
                    key,
                )
                kwargs.pop(key)

    def __ensure_dynamic_kwargs_where_specified(self, **kwargs: Any) -> None:
        for key, value in self._dynamic_specifiers.items():
            try:
                new_value = kwargs[key]
            except KeyError:
                raise Exception(f"Keyword argument {key!r} was not specified")

            if new_value not in value:
                raise Exception(
                    f"Keyword argument {new_value!r} is not allowed "
                    f"(allowed options: {value!r})"
                )

    def __ensure_no_additional_kwargs_where_specified(self, **kwargs: Any) -> None:
        for key in kwargs:
            if (
                key not in self._fixed_specifiers
                and self._dynamic_specifiers.get(key, None) is None
            ):
                raise Exception(f"Cannot pass additional keyword argument {key!r}")


class FrequencyParameter(Parameter):
    """Parameter instance with param type FREQUENCY and unit defaulting to MEGAHERTZ."""

    def __init__(
        self,
        *,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        units: Unit = default_units.frequency,
        default_value: float = 0.0,
        min_value: float | None = None,
        max_value: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_group=display_group,
            default_value=float(default_value),
            min_value=min_value,
            max_value=max_value,
            units=units,
            parameter_group=parameter_group,
            display_name_template=display_name_template,
            param_type=ParameterTypes.FREQUENCY,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> Freq:
        return Freq(value=float(database_value), unit=self._units)

    def _value_check(self, new_value: float) -> None:
        pass


class AmplitudeParameter(Parameter):
    """Parameter instance with param type AMPLITUDE and unit defaulting to PERCENT."""

    def __init__(
        self,
        *,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        units: Unit = default_units.amplitude,
        default_value: float = 0.0,
        min_value: float | None = 0.0,
        max_value: float | None = 100.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            default_value=float(default_value),
            display_group=display_group,
            min_value=min_value,
            max_value=max_value,
            units=units,
            parameter_group=parameter_group,
            display_name_template=display_name_template,
            param_type=ParameterTypes.AMPLITUDE,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> Amp:
        return Amp(value=float(database_value), unit=self._units)

    def _value_check(
        self,
        new_value: float,
    ) -> None:
        if not isinstance(new_value, float | int):
            raise TypeError("Trying to initialize an amplitude with a wrong type!")

        if new_value < 0 or new_value > 100:  # noqa: PLR2004
            raise ValueError(
                "Amplitude is given in percent, i.e. should be between 0 and 100"
            )


class TimeParameter(Parameter):
    """Parameter instance with param type TIME and unit defaulting to MICROSECOND."""

    def __init__(
        self,
        *,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        units: Unit = default_units.time,
        default_value: float = 2.0,
        min_value: float | None = 0.0,
        max_value: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            default_value=float(default_value),
            display_group=display_group,
            min_value=min_value,
            max_value=max_value,
            units=units,
            parameter_group=parameter_group,
            display_name_template=display_name_template,
            param_type=ParameterTypes.TIME,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> Time:
        return Time(value=float(database_value), unit=self._units)

    def _value_check(
        self,
        new_value: float,
    ) -> None:
        # TODO: convert to float?
        if not isinstance(new_value, float | int):
            raise TypeError("Trying to initialize a time with a wrong type")

        if new_value <= 1.4:  # noqa: PLR2004
            raise ValueError("Time should be greater than or equal to 1.4")


class PhaseParameter(Parameter):
    """Parameter instance with param type PHASE and unit defaulting to DEGREE."""

    def __init__(
        self,
        *,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        units: Unit = default_units.phase,
        default_value: float = 0.0,
        min_value: float | None = None,
        max_value: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            default_value=float(default_value),
            display_group=display_group,
            min_value=min_value,
            max_value=max_value,
            units=units,
            parameter_group=parameter_group,
            display_name_template=display_name_template,
            param_type=ParameterTypes.PHASE,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> Phase:
        return Phase(value=float(database_value), unit=self._units)

    def _value_check(self, new_value: float) -> None:
        pass  # check if number?


class BareCarrierFrequency(FrequencyParameter):
    """FrequencyParameter instance with frequency type BARE."""

    def __init__(
        self,
        *,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        units: Unit = default_units.frequency,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_group=display_group,
            units=units,
            parameter_group=parameter_group,
            display_name_template=display_name_template,
            frequency_type=FrequencyTypes.BARE,
            **kwargs,
        )


class StarkShiftFrequency(FrequencyParameter):
    """FrequencyParameter instance with frequency type BARE.

    Instances of this class can be used to query and set arbitrary values of stark
    shifts from the used database, e.g.

    ```python
    s = StarkShiftFrequency("Stark Shift")
    s.retrieve_parameter(transition=Transitions.Sp12_to_Dp52)
    s(transition=Transitions.Sp12_to_Dp52)
    ```
    """

    def __init__(
        self,
        *,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        units: Unit = default_units.frequency,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_group=display_group,
            units=units,
            parameter_group=parameter_group,
            display_name_template=display_name_template,
            frequency_type=FrequencyTypes.STARKSHIFT,
            **kwargs,
        )


class MotionalFrequency(FrequencyParameter):
    """FrequencyParameter instance with frequency type MOTIONAL."""

    def __init__(
        self,
        *,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        units: Unit = default_units.frequency,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_group=display_group,
            units=units,
            parameter_group=parameter_group,
            display_name_template=display_name_template,
            frequency_type=FrequencyTypes.MOTIONAL,
            **kwargs,
        )


class FrequencyOffset(FrequencyParameter):
    """FrequencyParameter instance with frequency type OFFSET."""

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            frequency_type=FrequencyTypes.OFFSET,
            **kwargs,
        )


class BooleanParameter(Parameter):
    """Parameter instance with param type BOOLEAN and no unit."""

    def __init__(
        self,
        default_value: bool = False,
        display_name_template: str = "{specifiers}",
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_group: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            default_value=default_value,
            display_group=display_group,
            display_name_template=display_name_template,
            parameter_group=parameter_group,
            units=Units.none,
            param_type=ParameterTypes.BOOLEAN,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> ISG_Parameter:
        return ISG_Parameter(value=bool(database_value), unit=self.units)

    def _value_check(self, new_value: float) -> None:
        pass


class IntegerParameter(Parameter):
    """Parameter instance with param type INT and no unit."""

    def __init__(
        self,
        default_value: int = 0,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_name_template=display_name_template,
            parameter_group=parameter_group,
            display_group=display_group,
            default_value=int(default_value),
            units=Units.none,
            param_type=ParameterTypes.INT,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> ISG_Parameter:
        return ISG_Parameter(value=int(database_value), unit=self.units)

    def _value_check(self, new_value: float) -> None:
        pass


class FloatParameter(Parameter):
    """Parameter instance with param type INT and no unit."""

    def __init__(
        self,
        default_value: float = 0.0,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_name_template=display_name_template,
            parameter_group=parameter_group,
            default_value=float(default_value),
            display_group=display_group,
            units=Units.none,
            param_type=ParameterTypes.FLOAT,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> ISG_Parameter:
        return ISG_Parameter(value=float(database_value), unit=self.units)

    def _value_check(self, new_value: float) -> None:
        pass


class ComboBoxParameter(Parameter):
    """Parameter instance with param type ENUM and no unit.

    The `ComboBoxParameter` is displayed as a dropdown menu in the frontend. Its
    `options` argument takes a list of the available options. The option types can be
    strings or enums. The first item in the list is taken as the default value.

    Example:
        ```python
        from pycrystal.parameters import ComboBoxParameter
        from pycrystal.utils.enums import BeamTypes

        combobox_param = ComboBoxParameter(
            options=[
                BeamTypes.BEAM_729,
                BeamTypes.BEAM_397,
                "other option",
            ]
        )

        option = combobox_param().value()  # returns one of the passed options
        ```
    """

    def __init__(
        self,
        options: list[str | Enum],
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_name_template=display_name_template,
            parameter_group=parameter_group,
            default_value=options[0].value
            if isinstance(options[0], Enum)
            else options[0],
            display_group=display_group,
            units=Units.none,
            param_type=ParameterTypes.ENUM,
            allowed_values=options,
            **kwargs,
        )

        if options is None:
            raise ValueError("No options set for this ComboBoxParameter.")

        self._allowed_value_map = {
            option.value if isinstance(option, Enum) else option: option
            for option in options
        }

    def _post_process(self, database_value: DatabaseValueType) -> ISG_Parameter:
        """Apply any necessary transformations to the value retrieved from the
        database."""

        if database_value in self._allowed_value_map:
            return ISG_Parameter(
                value=self._allowed_value_map[database_value], unit=self.units
            )

        raise ValueError(
            f"Could not parse value {database_value} received from database. "
            f"Expected one of: {self._allowed_values}"
        )

    def _value_check(self, new_value: float) -> None:
        pass


class StringParameter(Parameter):
    """Parameter instance with param type STRING and no unit."""

    def __init__(
        self,
        default_value: str = "",
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_name_template=display_name_template,
            parameter_group=parameter_group,
            display_group=display_group,
            default_value=str(default_value),
            units=Units.none,
            param_type=ParameterTypes.STRING,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> ISG_Parameter:
        return ISG_Parameter(value=str(database_value), unit=self.units)

    def _value_check(self, new_value: float) -> None:
        pass


class VoltageParameter(Parameter):
    """Parameter instance with param type VOLTAGE and unit VOLT."""

    def __init__(
        self,
        default_value: float = 0.0,
        parameter_group: str = DEFAULT_PARAMETER_GROUP,
        display_name_template: str = DEFAULT_DISPLAY_NAME_TEMPLATE,
        display_group: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            display_name_template=display_name_template,
            parameter_group=parameter_group,
            default_value=float(default_value),
            display_group=display_group,
            units=default_units.voltage,
            param_type=ParameterTypes.VOLTAGE,
            **kwargs,
        )

    def _post_process(self, database_value: DatabaseValueType) -> ISG_Parameter:
        return ISG_Parameter(value=float(database_value), unit=self.units)

    def _value_check(self, new_value: float) -> None:
        pass
