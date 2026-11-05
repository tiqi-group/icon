import asyncio
import importlib
import os
import sys
import venv
import warnings
from collections.abc import Iterator
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, call

import pytest

from icon.server.data_access import venv_exec
from icon.server.data_access.venv_exec import VirtualEnvironment
from tests.server.data_access import venv_callbacks

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


def test_venv_run_with_warnings() -> None:
    with TemporaryDirectory() as temp_dir, warnings.catch_warnings(record=True) as wrn:
        venv.EnvBuilder().create(temp_dir)
        env = VirtualEnvironment(temp_dir)

        warnings.simplefilter("always")
        return_value = asyncio.run(
            env.run(
                venv_callbacks.callback_with_warning,
                args={},
            )
        )
    assert len(wrn) == 1
    assert wrn[0].category is RuntimeWarning
    assert str(wrn[0].message) == "Some Warning"
    assert return_value == {"status": 0}


@pytest.fixture(scope="module")
def env() -> Iterator[VirtualEnvironment]:
    with TemporaryDirectory() as temp_dir:
        venv.EnvBuilder().create(temp_dir)
        yield VirtualEnvironment(temp_dir)


def test_reuse_venv_runs_the_calls_in_one_process(env: VirtualEnvironment) -> None:
    with env.reuse_venv():
        first = asyncio.run(env.run(venv_callbacks.process_id))
        second = asyncio.run(env.run(venv_callbacks.process_id))

    assert first == second
    assert asyncio.run(env.run(venv_callbacks.process_id)) != first


def test_process_of_a_single_call_exits(env: VirtualEnvironment) -> None:
    process_id = asyncio.run(env.run(venv_callbacks.process_id))

    with pytest.raises(ProcessLookupError):
        os.kill(process_id, 0)


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_output_and_warnings_are_logged(
    env: VirtualEnvironment, *, reuse_venv: bool
) -> None:
    logger = MagicMock()
    with env.reuse_venv() if reuse_venv else nullcontext():
        result = asyncio.run(
            env.run(venv_callbacks.callback_with_output, logger=logger)
        )

    assert result == "done"
    assert logger.warning.call_args_list == [call("to stdout\n"), call("Some Warning")]
    logger.error.assert_called_once_with("to stderr\nfrom C\n")


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_error_of_the_call_is_raised(
    env: VirtualEnvironment, *, reuse_venv: bool
) -> None:
    with (
        env.reuse_venv() if reuse_venv else nullcontext(),
        pytest.raises(RuntimeError, match="ValueError: bad sequence"),
    ):
        asyncio.run(env.run(venv_callbacks.failing_callback))


def test_reused_process_survives_an_error_of_the_call(
    env: VirtualEnvironment,
) -> None:
    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        with pytest.raises(RuntimeError):
            asyncio.run(env.run(venv_callbacks.failing_callback))

        assert asyncio.run(env.run(venv_callbacks.process_id)) == process_id


def test_reused_process_is_replaced_once_it_exits(env: VirtualEnvironment) -> None:
    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        with pytest.raises(RuntimeError, match="exited with return code 3"):
            asyncio.run(env.run(venv_callbacks.exiting_callback))

        assert asyncio.run(env.run(venv_callbacks.process_id)) != process_id


def test_reused_process_is_replaced_after_a_timeout(
    env: VirtualEnvironment, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(venv_exec, "CALL_TIMEOUT", 0.5)
    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        with pytest.raises(RuntimeError, match=r"timed out after 0\.5 s"):
            asyncio.run(env.run(venv_callbacks.slow_callback))

        assert asyncio.run(env.run(venv_callbacks.process_id)) != process_id


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_return_value_larger_than_the_pipe_buffer_is_transferred(
    env: VirtualEnvironment, *, reuse_venv: bool
) -> None:
    size = 2**21
    with env.reuse_venv() if reuse_venv else nullcontext():
        result = asyncio.run(
            env.run(venv_callbacks.large_instructions, args={"size": size})
        )

    assert result == venv_callbacks.large_instructions(size)
