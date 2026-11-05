"""Execute callables in isolated python environments."""

import asyncio
import dataclasses
import faulthandler
import json
import logging
import os
import pickle
import select
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import warnings
import weakref
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from typing import Any, BinaryIO, ClassVar

_logger = logging.getLogger(__name__)

CALL_TIMEOUT = 60.0
"""Seconds a call in the isolated environment may take."""

EXIT_TIMEOUT = 5.0
"""Seconds the runtime may take to exit before it is killed."""

MAX_MEMORY_GROWTH = 256 * 2**20
"""Bytes the memory of a reused runtime may grow by since its first call.

Beyond, it is replaced by a new one, so that a library which leaks memory, or keeps state
that grows with every call, cannot grow without bound over the calls of a long scan.
"""

_HEADER = struct.Struct(">Q")
"""Header of the messages to and from the runtime: the size of the rest."""


def noop_serialize(obj: Any) -> Any:
    """Default serialization / deserialization."""
    return obj


class VirtualEnvironment:
    """Representation of a python virtual environment."""

    def __init__(self, path: str) -> None:
        self.path = path
        # Preload the runtime (the `serve()` of this file) for the
        # isolated environment.
        # If we would directly pass this file as an argument of the
        # python exectuable, it would be recognized as a part of a
        # python package, which would cause import errors.
        with open(__file__) as f:
            self.venv_runtime = f.read()
        # Guards `_reuse_venv` and `_process`, which the threads of the calls use too
        self._lock = threading.Lock()
        self._reuse_venv = False
        # The reused process, only while reusing
        self._process: _RuntimeProcess | None = None

    @property
    def python_executable(self) -> str:
        return os.path.join(self.path, "bin", "python3")

    @contextmanager
    def reuse_venv(self) -> Generator[None]:
        """Run the calls in the context in one process, one after another.

        Starting the isolated environment for every call can take much longer than
        the call itself, mostly to import the modules again. The calls in the context
        share the state of the process, e.g. the imported modules, so changes to the
        code only take effect in the next context.

        A process whose memory grew by more than `MAX_MEMORY_GROWTH` since its first
        call is replaced by a new one after its call, which is logged as a warning. How
        much its memory grew is logged once the context ends.

        A call still running at the end of the context, of a caller that gave up on it,
        e.g. as it was interrupted, is stopped.
        """
        with self._lock:
            if self._reuse_venv:
                nested = True
            else:
                nested, self._reuse_venv = False, True
        if nested:
            yield
            return
        try:
            yield
        finally:
            with self._lock:
                self._reuse_venv = False
                process, self._process = self._process, None
            if process is not None:
                process.close()
                # A restarted one was reported on its restart
                if process.calls and not process.restarted:
                    _logger.info("Venv subprocess %s", process.memory_report())

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
        deserialized there and exectuted with arguments `**args`. Outside of
        `reuse_venv`, every call runs in a process of its own. The calls are made in
        threads of their own, see `shutdown`.

        The return value is transferred back to the calling environment.
        """
        python_path = [
            p for p in {module_path(callback), module_path(serialize)} if p is not None
        ]
        threads = _CallThreads.current()
        response, return_value = await asyncio.get_running_loop().run_in_executor(
            threads.executor,
            self._call,
            threads,
            # The paths to import the callback from come before the callback
            pickle.dumps(
                (python_path, pickle.dumps((callback, args or {}, serialize)))
            ),
        )

        if logger is not None:
            if response["stdout"].strip():
                logger.warning(response["stdout"])
            if response["stderr"].strip():
                logger.error(response["stderr"])

        if return_value is None:
            raise RuntimeError(f"Error executing code:\n{response['error']}")
        for warning, category in response["warnings"]:
            log_venv_warning(warning, category, logger=logger)
        return deserialize(json.loads(return_value))

    def _call(
        self, threads: "_CallThreads", request: bytes
    ) -> tuple[dict[str, Any], bytes | None]:
        """Make a call of `run` in the reused process, or in a process of its own.

        Runs in a thread of ``threads``, which start the process.

        Returns:
            Like `_RuntimeProcess.call`.
        """
        while True:
            with self._lock:
                if self._reuse_venv and (
                    self._process is None or self._process.restarted
                ):
                    self._process = threads.start_process(
                        self.python_executable, self.venv_runtime, reused=True
                    )
                process = self._process

            if process is None:
                process = threads.start_process(
                    self.python_executable, self.venv_runtime
                )
                try:
                    return process.call(request)
                finally:
                    process.close()

            try:
                return process.call(request)
            except _RestartedError:
                # The call of another thread restarted the process while this call
                # waited for it, so the call was not sent yet: make it in the new one
                continue
            except BaseException:
                # The failed call stopped the process, replaced by a new one on the
                # next call
                with self._lock:
                    if self._process is process:
                        self._process = None
                raise


class _CallThreads:
    """Threads making the venv calls of this process, see `VirtualEnvironment.run`.

    A pool of their own rather than asyncio's default one: a call holds its thread for
    up to `CALL_TIMEOUT`, so the calls must not take the threads of the other users of
    `asyncio.to_thread`, e.g. in the API server.

    A process waits for the threads on exit, so `shutdown` kills the processes the
    threads started, also those kept for reuse, which stops the running calls.
    """

    _current: ClassVar["_CallThreads | None"] = None
    _current_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(thread_name_prefix="venv")
        self._lock = threading.Lock()
        self._processes: weakref.WeakSet[_RuntimeProcess] = weakref.WeakSet()
        self._shut_down = False

    @classmethod
    def current(cls) -> "_CallThreads":
        """Return the threads of this process, started on first use."""
        with cls._current_lock:
            if cls._current is None:
                cls._current = cls()
            return cls._current

    @classmethod
    def shutdown_current(cls) -> None:
        """Shut down the threads of this process, see `shutdown`."""
        with cls._current_lock:
            current, cls._current = cls._current, None
        if current is not None:
            current.shutdown()

    @classmethod
    def forget_after_fork(cls) -> None:
        """Forget the threads of the parent in a forked child.

        The child has none of them, so their pool would never make its calls, and its
        shutdown must not kill the processes of the parent.
        """
        cls._current_lock = threading.Lock()
        cls._current = None

    def start_process(
        self, python_executable: str, runtime: str, *, reused: bool = False
    ) -> "_RuntimeProcess":
        """Start a process for calls, killed on shutdown.

        Raises:
            RuntimeError: The threads were shut down.
        """
        with self._lock:
            if self._shut_down:
                raise RuntimeError("Venv calls were shut down")
            process = _RuntimeProcess(python_executable, runtime, reused=reused)
            self._processes.add(process)
            return process

    def shutdown(self) -> None:
        """Kill the processes, which fails the running calls, and wait for the threads.

        Calls which did not start yet fail too, as they cannot start a process.
        """
        with self._lock:
            self._shut_down = True
            processes = list(self._processes)
        for process in processes:
            process.kill()
        self.executor.shutdown(wait=True)


os.register_at_fork(after_in_child=_CallThreads.forget_after_fork)


def shutdown() -> None:
    """Stop the venv calls of this process, and the threads making them.

    The process waits for the threads on exit, so without this, a call still running,
    e.g. of a task cancelled on exit, holds up the exit for up to `CALL_TIMEOUT`. The
    running calls fail, and later calls start new threads.
    """
    _CallThreads.shutdown_current()


class _RestartedError(RuntimeError):
    """The process was restarted before the call was sent to it."""


class _RuntimeProcess:
    """Process running one call after another in an isolated environment, see `serve`.

    A ``reused`` process restarts once its memory grew by more than
    `MAX_MEMORY_GROWTH`, see `VirtualEnvironment.reuse_venv`.
    """

    def __init__(
        self, python_executable: str, runtime: str, *, reused: bool = False
    ) -> None:
        self._reused = reused
        self.calls = 0
        """Number of calls the process responded to."""
        # Resident memory in bytes after the first call and after the last, while reused
        self._first_memory: int | None = None
        self._last_memory: int | None = None
        self.restarted = False
        """Whether it was stopped as its memory grew too much, to be replaced."""
        # Its stdout and stderr, files rather than pipes, so that nothing has to read
        # them while the process runs, and what it wrote is still there once it died,
        # e.g. why. `serve` takes the output of every call out of them. Closed by
        # `_stop`.
        self._output = (tempfile.TemporaryFile(), tempfile.TemporaryFile())  # noqa: SIM115
        # Pipes of their own, as anything can write to stdout, e.g. a .pth file of the
        # environment while the interpreter starts.
        request_read, request_write = os.pipe()
        response_read, response_write = os.pipe()
        try:
            self._process = subprocess.Popen(
                [
                    python_executable,
                    "-c",
                    runtime,
                    str(request_read),
                    str(response_write),
                ],
                stdin=subprocess.DEVNULL,
                stdout=self._output[0],
                stderr=self._output[1],
                pass_fds=(request_read, response_write),
                env={},
            )
        except BaseException:
            os.close(request_write)
            os.close(response_read)
            for file in self._output:
                file.close()
            raise
        finally:
            os.close(request_read)
            os.close(response_write)
        self._requests: BinaryIO | None = os.fdopen(request_write, "wb")
        self._responses: int | None = response_read
        self._lock = threading.Lock()

    def call(self, request: bytes) -> tuple[dict[str, Any], bytes | None]:
        """Send a request to the process and return the response.

        If the call raises, it stops the process: the rest of a response it read only
        in part would be taken for the response of the next call.

        A reused process restarts after the call if its memory grew too much.

        Returns:
            The response, and the return value encoded as JSON unless the call failed.

        Raises:
            RuntimeError: The process did not respond in time, or exited.
            _RestartedError: The process restarted before the call, which was not sent.
        """
        with self._lock:
            requests, responses = self._requests, self._responses
            if requests is None or responses is None:
                if self.restarted:
                    raise _RestartedError("Venv subprocess was restarted")
                raise RuntimeError("Venv subprocess was closed")
            try:
                requests.write(_HEADER.pack(len(request)) + request)
                requests.flush()
                deadline = time.monotonic() + CALL_TIMEOUT
                response = json.loads(self._read_message(responses, deadline))
                return_value = (
                    None
                    if "error" in response
                    else self._read_message(responses, deadline)
                )
            except TimeoutError:
                self._process.kill()
                output = self._stop()
                raise _error(
                    f"Venv subprocess timed out after {CALL_TIMEOUT:g} s", output
                ) from None
            except (BrokenPipeError, EOFError):
                output = self._stop()
                raise _error(
                    f"Venv subprocess {_describe_exit(self._process.returncode)}",
                    output,
                ) from None
            except BaseException:
                self._process.kill()
                self._close()
                raise
            self.calls += 1
            if self._reused:
                self._check_memory()
            return response, return_value

    def _check_memory(self) -> None:
        """Measure the memory after a call, and restart if it grew too much.

        Holds the lock, so no other call is running.
        """
        memory = self._measure_memory()
        if memory is None:
            return
        if self._first_memory is None:
            self._first_memory = memory
        self._last_memory = memory
        if memory - self._first_memory > MAX_MEMORY_GROWTH:
            _logger.warning(
                "Restarting the venv subprocess, as its memory grew by more than"
                " %.0f MiB: it %s",
                MAX_MEMORY_GROWTH / 2**20,
                self.memory_report(),
            )
            self.restarted = True
            self._close()

    def _measure_memory(self) -> int | None:
        """Return the resident memory of the process in bytes, None if unknown."""
        # Not at the top: this file is also the runtime in the isolated environment,
        # which may not have it
        import psutil  # noqa: PLC0415

        try:
            return psutil.Process(self._process.pid).memory_info().rss
        except psutil.Error:
            return None

    def memory_report(self) -> str:
        """Describe the calls the process made and how its memory changed over them."""
        calls = f"made {self.calls} call{'s' if self.calls != 1 else ''}"
        if self._first_memory is None or self._last_memory is None:
            return calls
        return (
            f"{calls}, its memory went from {self._first_memory / 2**20:.1f} MiB after"
            f" the first to {self._last_memory / 2**20:.1f} MiB after the last"
        )

    @classmethod
    def _read_message(cls, fd: int, deadline: float) -> bytes:
        """Read a message, preceded by its size, from ``fd``.

        Raises:
            Like `_read`.
        """
        (size,) = _HEADER.unpack(cls._read(fd, _HEADER.size, deadline))
        return cls._read(fd, size, deadline)

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

    def kill(self) -> None:
        """Kill the process, which fails a call running in it."""
        self._process.kill()

    def close(self) -> None:
        """Stop the process, which exits once its request pipe is closed.

        A call running in another thread is stopped by killing the process, rather than
        waited for.
        """
        if not self._lock.acquire(blocking=False):
            self.kill()
            self._lock.acquire()
        try:
            self._close()
        finally:
            self._lock.release()

    def _close(self) -> None:
        """Like `close`, holding the lock."""
        if (output := self._stop()).strip():
            _logger.warning("Venv subprocess wrote on exit:\n%s", output)

    def _stop(self) -> str:
        """Stop the process like `close`.

        Returns:
            What the process wrote to stdout and stderr since its last call, e.g. why it
            exited. Empty once the process was stopped before.
        """
        if self._requests is not None:
            # Flushing what a failed call could not send to the process fails again
            with suppress(OSError):
                self._requests.close()
            self._requests = None
        if self._responses is not None:
            os.close(self._responses)
            self._responses = None
        try:
            self._process.wait(timeout=EXIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
        output = ""
        for file in self._output:
            if not file.closed:
                file.seek(0)
                output += file.read().decode(errors="replace")
                file.close()
        return output


def _describe_exit(returncode: int) -> str:
    """Describe how a process exited, e.g. killed by the kernel for running out of memory."""
    description = f"exited with return code {returncode}"
    if returncode < 0:
        with suppress(ValueError):
            description += f" ({signal.Signals(-returncode).name})"
    return description


def _error(message: str, output: str) -> RuntimeError:
    """Create the error of a stopped process, with what it wrote, e.g. why it exited."""
    return RuntimeError(f"{message}:\n{output}" if output.strip() else message)


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


def serve(requests_fd: int, responses_fd: int) -> None:
    """Runtime for inside the isolated environment, running one call after another.

    Reads the calls from ``requests_fd`` and writes the responses to ``responses_fd``
    until the requests are closed, each message preceded by its size. A response holds
    what the call wrote to stdout and stderr, its warnings, and its error if it failed.
    Otherwise it is followed by the return value, in a message of its own so that a
    return value holding JSON strings, e.g. hardware instructions, is not encoded twice.

    Stdout and stderr are files, which the caller reads if the process dies, see
    `_captured_output`.
    """
    # Writes the traceback to stderr if the process crashes, e.g. on a segfault
    faulthandler.enable()
    with (
        os.fdopen(requests_fd, "rb") as requests,
        os.fdopen(responses_fd, "wb") as responses,
    ):
        while header := requests.read(_HEADER.size):
            (size,) = _HEADER.unpack(header)
            response, return_value = _handle_request(requests.read(size))
            messages = [json.dumps(response).encode()]
            if return_value is not None:
                messages.append(return_value)
            responses.write(b"".join(_HEADER.pack(len(m)) + m for m in messages))
            responses.flush()


def _handle_request(request: bytes) -> tuple[dict[str, Any], bytes | None]:
    """Run the call of a request to `serve`.

    Returns:
        The response, and the return value encoded as JSON unless the call failed.
    """
    response: dict[str, Any] = {}
    return_value = None
    with _captured_output() as output, warnings.catch_warnings(record=True) as wrn:
        warnings.simplefilter("always")
        try:
            python_path, payload = pickle.loads(request)
            for path in python_path:
                if path not in sys.path:
                    sys.path.append(path)
            callback, kwargs, serialize = pickle.loads(payload)
            return_value = json.dumps(serialize(callback(**kwargs))).encode()
        # A library calling `sys.exit` fails the call, not the process
        except (Exception, SystemExit):
            response["error"] = traceback.format_exc()
    response["warnings"] = [serialize_warning(w) for w in wrn]
    response["stdout"], response["stderr"] = output
    return response, return_value


@contextmanager
def _captured_output() -> Generator[list[str]]:
    """Capture what is written to stdout and stderr, also by extension modules.

    Stdout and stderr are files (see `_RuntimeProcess`), from which the output is taken
    on exit. So they hold what was written since the last call, which is what the caller
    reads if the process dies. What was written in between, e.g. while the interpreter
    started, is taken with the output of the call.

    Yields:
        The list the output to stdout and stderr is added to on exit.
    """
    captured: list[str] = []
    try:
        yield captured
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        captured.extend(_take_content(fd).decode(errors="replace") for fd in (1, 2))


def _take_content(fd: int) -> bytes:
    """Read the content of the file ``fd``, and remove it from the file."""
    os.lseek(fd, 0, os.SEEK_SET)
    content = bytearray()
    while chunk := os.read(fd, 1 << 16):
        content += chunk
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    return bytes(content)


def serialize_warning(w: warnings.WarningMessage) -> tuple[str, str]:
    return (format(w.message), w.category.__name__)


if __name__ == "__main__":
    serve(int(sys.argv[1]), int(sys.argv[2]))
