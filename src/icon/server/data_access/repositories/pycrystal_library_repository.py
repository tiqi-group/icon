import asyncio
import json
from pathlib import Path
from typing import Any
import sys
if sys.version_info < (3, 12):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

from icon.config.config import get_config
from icon.server.api.models.experiment_dict import (
    ExperimentDict,
)
from icon.server.api.models.parameter_metadata import (
    ParameterMetadata,
)
from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.data_access.repositories.experiment_data_repository import (
    ReadoutMetadata,
)

ParameterMetadataDict = TypedDict(
    "ParameterMetadataDict",
    {
        "all parameters": dict[str, ParameterMetadata],
        "display groups": dict[str, dict[str, ParameterMetadata]],
    },
)
"""Dictionary of parameter metadata."""


class ParameterAndExperimentMetadata(TypedDict):
    """Combined metadata for experiments and parameters."""

    experiment_metadata: ExperimentDict
    """Dictionary mapping the unique experiment identifier to its metadata."""
    parameter_metadata: ParameterMetadataDict
    """Dictionary of parameter metadata."""


class PycrystalLibraryRepository:
    """Repository for interacting with the `pycrystal` experiment library.

    Provides methods to fetch experiment and parameter metadata and to generate
    sequences by executing helper scripts inside the experiment library's virtual
    environment.
    """

    @staticmethod
    def _get_code(template_path: Path, **kwargs: Any) -> str:
        """Load and format a Python template file.

        Args:
            template_path: Path to the template file.
            **kwargs: Optional variables to substitute in the template.

        Returns:
            The resulting code string.
        """

        template = template_path.read_text()

        if kwargs:
            template = template.format(**kwargs)

        return template

    @staticmethod
    async def _run_code(code: str) -> str:
        """Execute generated Python code inside the experiment library's venv.

        Args:
            code: Python code to run.

        Returns:
            The standard output of the executed code.

        Raises:
            RuntimeError: If the process writes anything to stderr or the
                experiment_library.dir config option is not set.
        """

        exp_lib_dir = get_config().experiment_library.dir

        if not exp_lib_dir:
            raise RuntimeError("Config: experiment_library.dir is not defined")

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
        """Fetch the experiment and parameter metadata.

        Returns:
            Dictionary with experiment metadata and parameter metadata.
        """

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
        n_shots: int,
    ) -> str:
        """Generate a JSON sequence for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            JSON string containing the generated sequence.
        """

        template_vars = {
            "key_val_dict": parameter_dict,
            "module_name": exp_module_name,
            "exp_instance_name": exp_instance_name,
            "n_shots": n_shots,
        }

        code = PycrystalLibraryRepository._get_code(
            Path(__file__).parent.parent / "templates/generate_pycrystal_sequence.py",
            **template_vars,
        )
        return await PycrystalLibraryRepository._run_code(code)

    @staticmethod
    async def get_experiment_readout_metadata(
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: dict[str, DatabaseValueType],
    ) -> ReadoutMetadata:
        """Fetch readout metadata for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            Dictionary containing readout metadata for the experiment.
        """

        template_vars = {
            "key_val_dict": parameter_dict,
            "module_name": exp_module_name,
            "exp_instance_name": exp_instance_name,
        }

        code = PycrystalLibraryRepository._get_code(
            Path(__file__).parent.parent
            / "templates/get_experiment_readout_windows.py",
            **template_vars,
        )
        stdout = await PycrystalLibraryRepository._run_code(code)
        return json.loads(stdout)
