import json
from pathlib import Path
from typing import Any

from icon.server.data_access.repositories.experiments_repository import (
    ExperimentsRepository,
)


class ParametersRepository:
    @staticmethod
    async def get_parameter_metadata() -> dict[str, Any]:
        """Retrieve the experiments dictionary."""
        code = ExperimentsRepository._get_code(
            Path(__file__).parent.parent / "templates/get_pycrystal_parameters.py"
        )
        stdout = await ExperimentsRepository._run_code(code)
        return json.loads(stdout)
