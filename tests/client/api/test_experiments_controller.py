import pytest
from icon.client.api.experiments_controller import get_experiment_identifier_dict


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
