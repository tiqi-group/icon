"""Execute callables in isolated python environments."""

import asyncio
import json
import logging
import multiprocessing
import os
import pickle
import sys
import tempfile
from collections.abc import Callable
from typing import Any


class VirtualEnvironment:
    """Representation of a python virtual environment."""

    def __init__(self, path: str) -> None:
        self.path = path
        # Preload the runtime (the `main()` of this file) for the
        # isolated environment.
        # If we would directly pass this file as an argument of the
        # python exectuable, it would be recognized as a part of a
        # python package, which would cause import errors.
        with open(__file__) as f:
            self.venv_runtime = f.read()

    async def run(
        self,
        callback: Callable[..., Any],
        args: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,
    ) -> Any:
        """Run a callback in an isolated environment.

        The callable will be serialized, loaded inside the isolated environment,
        deserialized there and exectuted with arguments `**args`.

        The return value is transferred back to the calling environment.
        """
        python_executable = os.path.join(self.path, "bin", "python3")
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "out")
            payload = pickle.dumps((callback, args or {}, out_path))
            python_path = module_path(callback)
            proc = await asyncio.create_subprocess_exec(
                python_executable,
                "-c",
                self.venv_runtime,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                env={"PYTHONPATH": python_path} if python_path else {},
            )

            stdout, stderr = await proc.communicate(payload)

            if logger is not None:
                logger.warning(stdout.decode())
                logger.error(stderr.decode())

            if proc.returncode != 0:
                raise RuntimeError(
                    f"""Error executing code: return code: {proc.returncode}
{stderr.decode()}
"""
                )
            with open(out_path, "rb") as stream:  # noqa: ASYNC230
                return json.load(stream)


def module_path(obj: Any) -> str | None:
    """Return the path of the toplevel module of the module containing `obj`."""
    if not hasattr(obj, "__module__"):
        return None
    top_level_module = obj.__module__.split(".", 1)[0]
    if top_level_module == "builtins":
        return None
    path = sys.modules[top_level_module].__file__
    if path is None:
        msg = "Got a module without path"
        raise RuntimeError(msg)
    if os.path.basename(path) == "__init__.py":
        path = os.path.dirname(path)
    return os.path.dirname(path)


def main() -> None:
    """Runtime for inside the isolated environment."""
    in_data = sys.stdin.buffer.read()
    callback, kwargs, out_path = pickle.loads(in_data)
    out = callback(**kwargs)
    with open(out_path, "w") as stream:
        json.dump(out, stream)


if __name__ == "__main__":
    main()
