"""Execute callables in isolated python environments."""

import asyncio
import dataclasses
import json
import logging
import os
import pickle
import select
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from typing import Any

ENV_PATH_VAR = "ICON_VENV_EXEC_PATH"
"""ENV VAR for caller's import paths into the isolated environment."""

CALL_TIMEOUT = 60.0
"""Seconds a call in the isolated environment may take."""

SERVE_ARGUMENT = "serve"
"""Argument making the runtime run one call after another, see `serve`."""

EXIT_TIMEOUT = 5.0
"""Seconds a kept alive runtime may take to exit before it is killed."""

_HEADER = struct.Struct(">Q")
"""Header of the messages to and from a kept alive runtime: the size of the rest."""


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
        self._keep_alive = False
        self._process: _RuntimeProcess | None = None

    @property
    def python_executable(self) -> str:
        return os.path.join(self.path, "bin", "python3")

    @contextmanager
    def keep_alive(self) -> Iterator[None]:
        """Run the calls in the context in one process, one after another.

        Starting the isolated environment for every call can take much longer than
        the call itself, mostly to import the modules again. The calls in the context
        share the state of the process, e.g. the imported modules, so changes to the
        code only take effect in the next context.
        """
        if self._keep_alive:
            yield
            return
        self._keep_alive = True
        try:
            yield
        finally:
            self._keep_alive = False
            if self._process is not None:
                self._process.close()
                self._process = None

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
        python_path = [
            p for p in {module_path(callback), module_path(serialize)} if p is not None
        ]
        if self._keep_alive:
            stdout, stderr, error, out = await asyncio.to_thread(
                self._run_kept_alive,
                # The paths to import the callback from come before the callback
                pickle.dumps(
                    (python_path, pickle.dumps((callback, args or {}, serialize)))
                ),
            )
        else:
            stdout, stderr, error, out = await self._run_once(
                python_path, callback, args or {}, serialize
            )

        if logger is not None:
            if stdout.strip():
                logger.warning(stdout)
            if stderr.strip():
                logger.error(stderr)

        if error is not None:
            raise RuntimeError(error)
        return_value, wrn = out
        for warning, category in wrn:
            log_venv_warning(warning, category, logger=logger)
        return deserialize(return_value)

    async def _run_once(
        self,
        python_path: list[str],
        callback: Callable[..., Any],
        args: dict[str, Any],
        serialize: Callable[[Any], Any],
    ) -> tuple[str, str, str | None, Any]:
        """Run a callback in a process of its own.

        Returns:
            The output to stdout and stderr, the error if the call failed, and the
            return value and warnings otherwise.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "out")
            payload = pickle.dumps((callback, args, out_path, serialize))
            proc = await asyncio.create_subprocess_exec(
                self.python_executable,
                "-c",
                self.venv_runtime,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                env={ENV_PATH_VAR: os.pathsep.join(python_path)} if python_path else {},
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(payload), timeout=CALL_TIMEOUT
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise RuntimeError(
                    f"Venv subprocess timed out after {CALL_TIMEOUT:g} s"
                ) from None

            if proc.returncode != 0:
                error = f"""Error executing code: return code: {proc.returncode}
{stderr.decode()}
"""
                return stdout.decode(), stderr.decode(), error, None
            with open(out_path, "rb") as stream:  # noqa: ASYNC230
                return stdout.decode(), stderr.decode(), None, json.load(stream)

    def _run_kept_alive(self, request: bytes) -> tuple[str, str, str | None, Any]:
        """Run a call of `run` in the kept alive process, started on the first call.

        Returns:
            Like `_run_once`.
        """
        if self._process is None:
            self._process = _RuntimeProcess(self.python_executable, self.venv_runtime)
        try:
            response = self._process.call(request)
        except RuntimeError:
            # Replaced by a new process on the next call
            self._process.close()
            self._process = None
            raise
        if "error" in response:
            error = f"Error executing code:\n{response['error']}"
            return response["stdout"], response["stderr"], error, None
        return (
            response["stdout"],
            response["stderr"],
            None,
            (json.loads(response["return_value"]), response["warnings"]),
        )


class _RuntimeProcess:
    """Process running one call after another in an isolated environment, see `serve`."""

    def __init__(self, python_executable: str, runtime: str) -> None:
        self._process = subprocess.Popen(
            [python_executable, "-c", runtime, SERVE_ARGUMENT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env={},
        )
        self._lock = threading.Lock()

    def call(self, request: bytes) -> dict[str, Any]:
        """Send a request to the process and return the response.

        Raises:
            RuntimeError: The process did not respond in time, or exited.
        """
        stdin, stdout = self._process.stdin, self._process.stdout
        if stdin is None or stdout is None:
            raise RuntimeError("Venv subprocess was closed")
        with self._lock:
            try:
                stdin.write(_HEADER.pack(len(request)) + request)
                stdin.flush()
                deadline = time.monotonic() + CALL_TIMEOUT
                (size,) = _HEADER.unpack(
                    self._read(stdout.fileno(), _HEADER.size, deadline)
                )
                return json.loads(self._read(stdout.fileno(), size, deadline))
            except TimeoutError:
                self._process.kill()
                raise RuntimeError(
                    f"Venv subprocess timed out after {CALL_TIMEOUT:g} s"
                ) from None
            except (BrokenPipeError, EOFError):
                self.close()
                raise RuntimeError(
                    "Venv subprocess exited with return code "
                    f"{self._process.returncode}"
                ) from None

    @staticmethod
    def _read(fd: int, size: int, deadline: float) -> bytes:
        """Read ``size`` bytes from ``fd``.

        Raises:
            TimeoutError: The bytes did not arrive by ``deadline``.
            EOFError: The stream ended before.
        """
        data = bytearray()
        while len(data) < size:
            ready, _, _ = select.select(
                [fd], [], [], max(deadline - time.monotonic(), 0)
            )
            if not ready:
                raise TimeoutError
            chunk = os.read(fd, size - len(data))
            if not chunk:
                raise EOFError
            data += chunk
        return bytes(data)

    def close(self) -> None:
        """Stop the process, which exits once its stdin is closed."""
        for stream in (self._process.stdin, self._process.stdout):
            # Flushing what a failed call could not send to the process fails again
            with suppress(OSError):
                if stream is not None:
                    stream.close()
        try:
            self._process.wait(timeout=EXIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()


def log_venv_warning(
    message: str, category: str, logger: logging.Logger | None
) -> None:
    if logger is None:
        warnings.warn(
            message, category=getattr(sys.modules["builtins"], category), stacklevel=0
        )
    else:
        logger.warning(message)


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
    for path in os.environ.get(ENV_PATH_VAR, "").split(os.pathsep):
        if path and path not in sys.path:
            sys.path.append(path)

    in_data = sys.stdin.buffer.read()
    callback, kwargs, out_path, serialize = pickle.loads(in_data)
    with warnings.catch_warnings(record=True) as wrn:
        warnings.simplefilter("always")
        out = callback(**kwargs)
    with open(out_path, "w") as stream:
        json.dump((serialize(out), [serialize_warning(w) for w in wrn]), stream)


def serve() -> None:
    """Runtime for inside the isolated environment, running one call after another.

    Reads the calls from stdin and writes the responses to stdout until stdin is
    closed, each message preceded by its size. A response holds what the call wrote
    to stdout and stderr, its warnings, and its return value or error.
    """
    with os.fdopen(os.dup(1), "wb") as responses:
        # Keeps what is written outside of the calls, e.g. on exit, off the responses
        os.dup2(2, 1)
        requests = sys.stdin.buffer
        while header := requests.read(_HEADER.size):
            (size,) = _HEADER.unpack(header)
            response = json.dumps(_call(requests.read(size))).encode()
            responses.write(_HEADER.pack(len(response)) + response)
            responses.flush()


def _call(request: bytes) -> dict[str, Any]:
    """Run a call of `serve`."""
    response: dict[str, Any] = {}
    with _captured_output() as output, warnings.catch_warnings(record=True) as wrn:
        warnings.simplefilter("always")
        try:
            python_path, payload = pickle.loads(request)
            for path in python_path:
                if path not in sys.path:
                    sys.path.append(path)
            callback, kwargs, serialize = pickle.loads(payload)
            response["return_value"] = json.dumps(serialize(callback(**kwargs)))
        except Exception:
            response["error"] = traceback.format_exc()
    response["warnings"] = [serialize_warning(w) for w in wrn]
    response["stdout"], response["stderr"] = output
    return response


@contextmanager
def _captured_output() -> Iterator[list[str]]:
    """Capture what is written to stdout and stderr, also by extension modules.

    Yields:
        The list the output to stdout and stderr is added to on exit.
    """
    captured: list[str] = []
    saved = [os.dup(1), os.dup(2)]
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(stdout.fileno(), 1)
        os.dup2(stderr.fileno(), 2)
        try:
            yield captured
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            for fd, saved_fd in zip((1, 2), saved, strict=True):
                os.dup2(saved_fd, fd)
                os.close(saved_fd)
            for file in (stdout, stderr):
                file.seek(0)
                captured.append(file.read().decode(errors="replace"))


def serialize_warning(w: warnings.WarningMessage) -> tuple[str, str]:
    return (format(w.message), w.category.__name__)


if __name__ == "__main__":
    if sys.argv[1:] == [SERVE_ARGUMENT]:
        serve()
    else:
        main()
