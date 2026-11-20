from pathlib import Path

import sqlalchemy
from sqlalchemy.engine import Engine


class CachedEngine:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._engine = create_engine(self.path)

    def get_cached(self, path: str | Path) -> Engine:
        path = Path(path)
        if path != self.path:
            self._engine.dispose()
            self._engine = create_engine(path)
            self.path = path
        return self._engine


def create_engine(path: Path) -> Engine:
    if not path.parent.exists():
        path.parent.mkdir()
    return sqlalchemy.create_engine(f"sqlite:///{path}", echo=False)
