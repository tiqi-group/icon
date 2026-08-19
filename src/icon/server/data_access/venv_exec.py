"""Execute callables in isolated python environments."""

import asyncio
import dataclasses
import json
import logging
import os
import pickle
import sys
import tempfile
from collections.abc import Callable
from typing import Any

PERSISTENT_WORKER_ARG = "--persistent-worker"
"""Argument marking a `venv_exec` subprocess as a long-lived worker (see `main`)."""

LENGTH_PREFIX_SIZE = 4
"""Byte size of the big-endian message-length prefix used by the worker protocol."""


def noop_serialize(obj: Any) -> Any:
    """Default serialization / deserialization."""
    return obj


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
        serialize: Callable[[Any], Any] = noop_serialize,
        deserialize: Callable[[Any], Any] = noop_serialize,
    ) -> Any:
        """Run a callback in an isolated environment.

        The callable will be serialized, loaded inside the isolated environment,
        deserialized there and exectuted with arguments `**args`.

        The return value is transferred back to the calling environment.
        """
        python_executable = os.path.join(self.path, "bin", "python3")
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "out")
            payload = pickle.dumps((callback, args or {}, out_path, serialize))
            python_path = combined_module_path(callback, serialize, deserialize)
            proc = await asyncio.create_subprocess_exec(
                python_executable,
                "-c",
                self.venv_runtime,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                env={"PYTHONPATH": python_path} if python_path else {},
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(payload), timeout=60.0
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise RuntimeError("Venv subprocess timed out after 60 s") from None

            if logger is not None:
                if stdout:
                    logger.warning(stdout.decode())
                if stderr:
                    logger.error(stderr.decode())

            if proc.returncode != 0:
                raise RuntimeError(
                    f"""Error executing code: return code: {proc.returncode}
{stderr.decode()}
"""
                )
            with open(out_path, "rb") as stream:  # noqa: ASYNC230
                return deserialize(json.load(stream))

    async def start_worker(
        self,
        callback: Callable[..., Any],
        serialize: Callable[[Any], Any] = noop_serialize,
        deserialize: Callable[[Any], Any] = noop_serialize,
    ) -> "VenvWorker":
        """Start a long-lived subprocess for repeated calls via `VenvWorker.run`.

        Unlike `run`, which spawns and tears down a subprocess for every
        call, the interpreter here keeps running across calls -- useful when
        a caller expects to make many calls in a row (e.g. once per job) and
        spawning a fresh interpreter each time would be wasteful.

        `PYTHONPATH` for the subprocess is derived from `callback`,
        `serialize` and `deserialize` (same as `run`) and fixed for the
        worker's entire lifetime, so every call made through it via
        `VenvWorker.run` must use the same `callback`/`serialize`/
        `deserialize` combination passed here.
        """
        python_executable = os.path.join(self.path, "bin", "python3")
        python_path = combined_module_path(callback, serialize, deserialize)
        process = await asyncio.create_subprocess_exec(
            python_executable,
            "-c",
            self.venv_runtime,
            PERSISTENT_WORKER_ARG,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={"PYTHONPATH": python_path} if python_path else {},
        )
        return VenvWorker(process)


class VenvWorker:
    """A long-lived `venv_exec` subprocess, reused across multiple `run` calls."""

    def __init__(self, process: "asyncio.subprocess.Process") -> None:
        self._process = process

    async def run(
        self,
        callback: Callable[..., Any],
        args: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,  # noqa: ARG002
        serialize: Callable[[Any], Any] = noop_serialize,
        deserialize: Callable[[Any], Any] = noop_serialize,
    ) -> Any:
        """Run a callback in the worker's isolated environment.

        Same calling convention as `VirtualEnvironment.run`, but reuses the
        subprocess started by `start_worker` instead of spawning a new one.
        """
        stdin, stdout = self._process.stdin, self._process.stdout
        if stdin is None or stdout is None:
            raise RuntimeError("Worker subprocess has no stdin/stdout pipe")

        payload = pickle.dumps((callback, args or {}, serialize))
        stdin.write(len(payload).to_bytes(LENGTH_PREFIX_SIZE, "big") + payload)
        await stdin.drain()

        length = int.from_bytes(await stdout.readexactly(LENGTH_PREFIX_SIZE), "big")
        body = await stdout.readexactly(length)
        response = json.loads(body)

        if "error" in response:
            raise RuntimeError(f"Error executing code in worker: {response['error']}")

        return deserialize(response["result"])

    async def stop(self) -> None:
        """Shut down the subprocess, waiting briefly for a clean exit."""
        if self._process.returncode is not None:
            return
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()


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


def combined_module_path(*objs: Any) -> str:
    """`PYTHONPATH` value covering every object in `objs` (see `module_path`)."""
    return ":".join(
        p for p in dict.fromkeys(module_path(obj) for obj in objs) if p is not None
    )


def deep_asdict(
    data: Any,
) -> Any:
    """Variant of dataclasses.asdict which also allows non dataclass objects."""

    @dataclasses.dataclass
    class Container:
        obj: Any

    return dataclasses.asdict(Container(data))["obj"]


def main() -> None:
    """Runtime for inside the isolated environment."""
    if PERSISTENT_WORKER_ARG in sys.argv[1:]:
        _run_persistent_worker()
    else:
        _run_once()


def _run_once() -> None:
    """Run a single call, taking it from stdin and writing its result to a file.

    Matches `VirtualEnvironment.run`, which spawns one subprocess per call.
    """
    in_data = sys.stdin.buffer.read()
    callback, kwargs, out_path, serialize = pickle.loads(in_data)
    out = callback(**kwargs)
    with open(out_path, "w") as stream:
        json.dump(serialize(out), stream)


def _run_persistent_worker() -> None:
    """Serve calls read from stdin, one at a time, until stdin is closed.

    Matches `VenvWorker.run`/`VirtualEnvironment.start_worker`: each call is a
    length-prefixed pickled `(callback, kwargs, serialize)`, and each
    response is a length-prefixed JSON object with either a "result" or an
    "error" key. A failing call does not stop the worker -- it is reported
    back so the caller can decide what to do -- since the worker is expected
    to keep serving further calls for the rest of its caller's job.
    """
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        length_bytes = stdin.read(LENGTH_PREFIX_SIZE)
        if len(length_bytes) < LENGTH_PREFIX_SIZE:
            return
        length = int.from_bytes(length_bytes, "big")
        payload = stdin.read(length)
        callback, kwargs, serialize = pickle.loads(payload)

        try:
            response: dict[str, Any] = {"result": serialize(callback(**kwargs))}
        except Exception as exc:
            response = {"error": f"{type(exc).__name__}: {exc}"}

        body = json.dumps(response).encode()
        stdout.write(len(body).to_bytes(LENGTH_PREFIX_SIZE, "big") + body)
        stdout.flush()


if __name__ == "__main__":
    main()
