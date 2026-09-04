import asyncio
import importlib
import sys
import venv
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory

from icon.server.data_access.venv_exec import VirtualEnvironment

HERE = Path(__file__).parent


def test_venv_run() -> None:
    sys.path.append(str(HERE / "mock_experiment_library_client"))
    client_module = importlib.import_module("mock_client")
    with TemporaryDirectory() as temp_dir:
        venv.EnvBuilder().create(temp_dir)
        env = VirtualEnvironment(temp_dir)

        client = client_module.MockExperimentLibraryClient()
        result = asyncio.run(
            env.run(
                client.generate_json_sequence,
                args={
                    "exp_module_name": "...",
                    "exp_instance_name": "...",
                    "parameter_dict": {},
                    "n_shots": 1,
                },
            )
        )
    assert result == "{}"


def callback_with_warning() -> dict[str, int]:
    warnings.warn("Some Warning", category=RuntimeWarning, stacklevel=42)
    return {"status": 0}


def test_venv_run_with_warnings() -> None:
    with TemporaryDirectory() as temp_dir, warnings.catch_warnings(record=True) as wrn:
        venv.EnvBuilder().create(temp_dir)
        env = VirtualEnvironment(temp_dir)

        warnings.simplefilter("always")
        return_value = asyncio.run(
            env.run(
                callback_with_warning,
                args={},
            )
        )
    assert len(wrn) == 1
    assert wrn[0].category is RuntimeWarning
    assert str(wrn[0].message) == "Some Warning"
    assert return_value == {"status": 0}
