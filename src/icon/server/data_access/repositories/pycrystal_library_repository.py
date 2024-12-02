import asyncio
import json
from pathlib import Path
from typing import Any

from icon.config.config import get_config


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
        python_executable = (
            Path(get_config().experiment_library.dir) / ".venv/bin/python3"
        )
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
    async def get_experiment_and_parameter_metadata() -> dict[str, Any]:
        """Retrieve the experiments dictionary."""
        code = PycrystalLibraryRepository._get_code(
            Path(__file__).parent.parent
            / "templates/get_pycrystal_experiment_and_parameter_metadata.py"
        )
        stdout = await PycrystalLibraryRepository._run_code(code)
        return json.loads(stdout)
