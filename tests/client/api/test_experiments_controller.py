import pytest

from icon.client.api.experiments_controller import (
    get_experiment_identifier_dict,
    get_parameter_identifier_mapping,
)
from icon.server.api.models.parameter_metadata import (
    ParameterMetadata,
)


@pytest.mark.parametrize(
    "experiments, expected",
    [
        # Test case: All instance names are unique
        (
            [
                "experiment_library.experiments.ramsey_experiment.RamseyExperiment (Ramsey 1)",
                "experiment_library.experiments.ramsey_experiment.RamseyExperiment (Ramsey 2)",
                "experiment_library.experiments.exp_tickle.Tickle (Tickle)",
            ],
            {
                "Ramsey 1": "experiment_library.experiments.ramsey_experiment.RamseyExperiment (Ramsey 1)",
                "Ramsey 2": "experiment_library.experiments.ramsey_experiment.RamseyExperiment (Ramsey 2)",
                "Tickle": "experiment_library.experiments.exp_tickle.Tickle (Tickle)",
            },
        ),
        # Test case: Non-unique instance names
        (
            [
                "experiment_library.experiments.ramsey_experiment.RamseyExperiment (Ramsey 1)",
                "experiment_library.experiments.exp_tickle.Tickle (Ramsey 1)",
                "experiment_library.experiments.exp_tickle.Tickle (Tickle)",
            ],
            {
                "Ramsey 1 (RamseyExperiment)": "experiment_library.experiments.ramsey_experiment.RamseyExperiment (Ramsey 1)",
                "Ramsey 1 (Tickle)": "experiment_library.experiments.exp_tickle.Tickle (Ramsey 1)",
                "Tickle": "experiment_library.experiments.exp_tickle.Tickle (Tickle)",
            },
        ),
        # Test case: Empty list
        (
            [],
            {},
        ),
    ],
)
def test_get_experiment_identifier_dict(
    experiments: list[str], expected: dict[str, str]
) -> None:
    result = get_experiment_identifier_dict(experiments)
    assert result == expected


@pytest.mark.parametrize(
    "input_metadata,expected_output",
    [
        # Basic case
        (
            {
                "param 1": {
                    "display_name": "Tickle time",
                    "unit": "us",
                    "default_value": 2.0,
                    "min_value": 1.4,
                    "max_value": None,
                },
                "param 2": {
                    "display_name": "Tickle frequency",
                    "unit": "MHz",
                    "default_value": 0.0,
                    "min_value": None,
                    "max_value": None,
                },
                "param 3": {
                    "display_name": "Tickle amplitude",
                    "unit": "%",
                    "default_value": 0.0,
                    "min_value": 0.0,
                    "max_value": 100.0,
                },
            },
            {
                "Tickle time": "param 1",
                "Tickle frequency": "param 2",
                "Tickle amplitude": "param 3",
            },
        ),
        # Empty input
        ({}, {}),
        # Duplicate display names
        (
            {
                "param1": {
                    "display_name": "Duplicate Name",
                    "unit": "unit",
                    "default_value": 1.0,
                    "min_value": None,
                    "max_value": None,
                },
                "param2": {
                    "display_name": "Duplicate Name",
                    "unit": "unit",
                    "default_value": 2.0,
                    "min_value": 0.0,
                    "max_value": 10.0,
                },
            },
            {
                "Duplicate Name": "param2"  # Last occurrence overrides
            },
        ),
    ],
)
def test_get_parameter_identifier_mapping(
    input_metadata: dict[str, ParameterMetadata], expected_output: dict[str, str]
) -> None:
    assert get_parameter_identifier_mapping(input_metadata) == expected_output
