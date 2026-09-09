"""Experiment library client used by the command line tools.

The tools in this package inspect a library a developer is editing, which the clients in
:mod:`icon.server.data_access.pycrystal_experiment_library_client` cannot do: those clone
a repository and check out a revision. Hence the local-working-tree client here.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from icon.server.data_access.pycrystal_experiment_library_client import PyCrystalClient
from icon.server.data_access.venv_experiment_library_client import (
    VEnvExperimentLibraryClient,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from icon.server.data_access.experiment_library_client import (
        ExperimentLibraryClient,
    )

# The name the experiment library plumbing logs under, shared with the clients this one
# sits beside.
logger = logging.getLogger("experiment_library")


class LocalPyCrystalClient(VEnvExperimentLibraryClient):
    """Run a pycrystal experiment library straight from a local directory.

    Unlike :class:`AsyncPyCrystalClient` this does no git work at all: `checkout_path`
    points at a working tree that already exists, so there is no repository to clone and
    no revision to check out. Intended for development against a library you are editing
    - notably through ``python -m icon.cli.cmd_experiment_library``.

    The library still runs in its own interpreter, `<checkout_path>/.venv`, exactly as it
    does in production, so this exercises the same import and serialization path as
    :class:`AsyncPyCrystalClient`.

    Args:
        checkout_path: Directory holding the experiment library and its `.venv`.
        experiment_library_module: Importable name of the library package.
    """

    def __init__(
        self,
        checkout_path: str,
        experiment_library_module: str = "experiment_library",
    ) -> None:
        super().__init__(
            client=PyCrystalClient(experiment_library_module),
            venv_path=str(Path(checkout_path) / ".venv"),
        )
        self.checkout_path = checkout_path
        self.experiment_library_module = experiment_library_module

    def checkout_revision(self, revision: str | None) -> str | None:
        """Return the local path; a working tree has no revision to restore."""
        if revision is not None:
            logger.warning(
                "Ignoring revision %r: %s reads the working tree at %s as-is.",
                revision,
                type(self).__name__,
                self.checkout_path,
            )
        return self.checkout_path

    @contextmanager
    def isolated(self) -> Iterator[ExperimentLibraryClient]:
        """Yield this client; a local working tree is never copied."""
        yield self
