from pathlib import Path

from pydantic import BaseModel


class Experiment(BaseModel):
    git_commit_hash: str | None = None
    file_path: Path
    name: str
