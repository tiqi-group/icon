#!/bin/env python3

import asyncio
import importlib
import sys
import venv
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
