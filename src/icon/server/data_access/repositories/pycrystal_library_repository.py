import asyncio
import json
from pathlib import Path
from typing import Any, TypedDict

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.data_access.repositories.experiment_metadata_repository import (
    ExperimentDict,
)
from icon.server.data_access.repositories.parameter_metadata_repository import (
    ParameterMetadata,
)

ParameterMetadataDict = TypedDict(
    "ParameterMetadataDict",
    {
        "all parameters": dict[str, ParameterMetadata],
        "display groups": dict[str, dict[str, ParameterMetadata]],
    },
)


class ParameterAndExperimentMetadata(TypedDict):
    experiment_metadata: ExperimentDict
    parameter_metadata: ParameterMetadataDict


class PycrystalLibraryRepository:
    @staticmethod
    def _get_code(template_path: Path, **kwargs: Any) -> str:
        template = template_path.read_text()

        if kwargs:
            template = template.format(**kwargs)

        return template

    @staticmethod
    async def _run_code(code: str) -> str:
        """Run the generated Python code in the specified virtual environment."""
        exp_lib_dir = get_config().experiment_library.dir
        if exp_lib_dir.startswith("../"):
            exp_lib_dir = (
                str(Path(__file__).parent.parent.parent.parent.parent.parent)
                + f"/{exp_lib_dir}"
            )

        python_executable = Path(exp_lib_dir) / ".venv/bin/python3"
        proc = await asyncio.create_subprocess_exec(
            str(python_executable),
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if stderr:
            raise RuntimeError(f"Error executing code: {stderr.decode()}")

        return stdout.decode()

    @staticmethod
    async def get_experiment_and_parameter_metadata() -> ParameterAndExperimentMetadata:
        """Retrieve the experiments dictionary."""
        code = PycrystalLibraryRepository._get_code(
            Path(__file__).parent.parent
            / "templates/get_pycrystal_experiment_and_parameter_metadata.py"
        )
        stdout = await PycrystalLibraryRepository._run_code(code)
        return json.loads(stdout)

    @staticmethod
    async def generate_json_sequence(
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: dict[str, DatabaseValueType],
    ) -> str:
        template_vars = {
            "key_val_dict": parameter_dict,
            "module_name": exp_module_name,
            "exp_instance_name": exp_instance_name,
        }

        code = PycrystalLibraryRepository._get_code(
            Path(__file__).parent.parent / "templates/generate_pycrystal_sequence.py",
            **template_vars,
        )
        return await PycrystalLibraryRepository._run_code(code)
