import asyncio
import importlib
import json
import logging
import multiprocessing
import os
import re
import sys
import threading
import time
import venv
import warnings
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext, suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, call

import pytest

from icon.server.data_access import venv_exec
from icon.server.data_access.venv_exec import VirtualEnvironment
from tests.server.data_access import venv_callbacks

HERE = Path(__file__).parent


@pytest.fixture(autouse=True, scope="module")
def _stop_the_threads_of_the_calls() -> Iterator[None]:
    """Keep them from making later tests fork a process with threads."""
    yield
    venv_exec.shutdown()


def test_venv_run() -> None:
    sys.path.append(str(HERE / "mock_experiment_library_client"))
    client_module = importlib.import_module("mock_client")
    with TemporaryDirectory() as temp_dir:
        venv.EnvBuilder().create(temp_dir)
        env = VirtualEnvironment(temp_dir)

        client = client_module.MockExperimentLibraryClient()
        result = asyncio.run(
            env.run(
                client.generate_json_sequence,
                args={
                    "exp_module_name": "...",
                    "exp_instance_name": "...",
                    "parameter_dict": {},
                    "n_shots": 1,
                },
            )
        )
    assert result == "{}"


def test_venv_run_with_warnings() -> None:
    with TemporaryDirectory() as temp_dir, warnings.catch_warnings(record=True) as wrn:
        venv.EnvBuilder().create(temp_dir)
        env = VirtualEnvironment(temp_dir)

        warnings.simplefilter("always")
        return_value = asyncio.run(
            env.run(
                venv_callbacks.callback_with_warning,
                args={},
            )
        )
    assert len(wrn) == 1
    assert wrn[0].category is RuntimeWarning
    assert str(wrn[0].message) == "Some Warning"
    assert return_value == {"status": 0}


@pytest.fixture(scope="module")
def env() -> Iterator[VirtualEnvironment]:
    with TemporaryDirectory() as temp_dir:
        venv.EnvBuilder().create(temp_dir)
        yield VirtualEnvironment(temp_dir)


def test_reuse_venv_runs_the_calls_in_one_process(env: VirtualEnvironment) -> None:
    with env.reuse_venv():
        first = asyncio.run(env.run(venv_callbacks.process_id))
        second = asyncio.run(env.run(venv_callbacks.process_id))

    assert first == second
    assert asyncio.run(env.run(venv_callbacks.process_id)) != first


def test_process_of_a_single_call_exits(env: VirtualEnvironment) -> None:
    process_id = asyncio.run(env.run(venv_callbacks.process_id))

    with pytest.raises(ProcessLookupError):
        os.kill(process_id, 0)


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_output_and_warnings_are_logged(
    env: VirtualEnvironment, *, reuse_venv: bool
) -> None:
    logger = MagicMock()
    with env.reuse_venv() if reuse_venv else nullcontext():
        result = asyncio.run(
            env.run(venv_callbacks.callback_with_output, logger=logger)
        )

    assert result == "done"
    assert logger.warning.call_args_list == [call("to stdout\n"), call("Some Warning")]
    logger.error.assert_called_once_with("to stderr\nfrom C\n")


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_error_of_the_call_is_raised(
    env: VirtualEnvironment, *, reuse_venv: bool
) -> None:
    with (
        env.reuse_venv() if reuse_venv else nullcontext(),
        pytest.raises(RuntimeError, match="ValueError: bad sequence"),
    ):
        asyncio.run(env.run(venv_callbacks.failing_callback))


@pytest.mark.parametrize(
    ("callback", "error"),
    [
        (venv_callbacks.failing_callback, "ValueError: bad sequence"),
        (venv_callbacks.sys_exiting_callback, "SystemExit: library gave up"),
    ],
)
def test_reused_process_survives_an_error_of_the_call(
    env: VirtualEnvironment, callback: Callable[[], None], error: str
) -> None:
    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        with pytest.raises(RuntimeError, match=error):
            asyncio.run(env.run(callback))

        assert asyncio.run(env.run(venv_callbacks.process_id)) == process_id


def test_reused_process_is_replaced_once_it_exits(env: VirtualEnvironment) -> None:
    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        with pytest.raises(RuntimeError, match="exited with return code 3"):
            asyncio.run(env.run(venv_callbacks.exiting_callback))

        assert asyncio.run(env.run(venv_callbacks.process_id)) != process_id


@pytest.mark.parametrize("reuse_venv", [False, True])
@pytest.mark.parametrize(
    ("callback", "expected"),
    [
        (
            venv_callbacks.exiting_callback,
            [
                "exited with return code 3:\n",
                "to stdout before exiting\n",
                "giving up\n",
            ],
        ),
        (venv_callbacks.killed_callback, ["exited with return code -9 (SIGKILL)"]),
        (
            venv_callbacks.segfaulting_callback,
            [
                "exited with return code -11 (SIGSEGV):\n",
                "Fatal Python error: Segmentation fault",
                "in segfaulting_callback",
            ],
        ),
    ],
)
def test_error_of_a_dead_process_holds_what_it_wrote(
    env: VirtualEnvironment,
    callback: Callable[[], None],
    expected: list[str],
    *,
    reuse_venv: bool,
) -> None:
    with (
        env.reuse_venv() if reuse_venv else nullcontext(),
        pytest.raises(RuntimeError) as error,
    ):
        asyncio.run(env.run(callback))

    for text in expected:
        assert text in str(error.value)


@pytest.mark.parametrize(
    ("size", "body", "error"),
    [
        (3, "bad", json.JSONDecodeError),
        # A garbage size, larger than the memory
        (2**62, "", MemoryError),
    ],
)
def test_reused_process_is_replaced_after_a_malformed_response(
    env: VirtualEnvironment, size: int, body: str, error: type[BaseException]
) -> None:
    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        with pytest.raises(error):
            asyncio.run(
                env.run(
                    venv_callbacks.callback_writing_a_malformed_response,
                    args={"size": size, "body": body},
                )
            )

        with pytest.raises(ProcessLookupError):
            os.kill(process_id, 0)
        # Not the rest of the response of the malformed one
        new_process_id = asyncio.run(env.run(venv_callbacks.process_id))
        assert isinstance(new_process_id, int)
        assert new_process_id != process_id


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_output_on_exit_of_the_process_is_logged(
    env: VirtualEnvironment, caplog: pytest.LogCaptureFixture, *, reuse_venv: bool
) -> None:
    with env.reuse_venv() if reuse_venv else nullcontext():
        asyncio.run(env.run(venv_callbacks.callback_writing_on_exit))

    assert caplog.messages == ["Venv subprocess wrote on exit:\nbye\n"]


def test_reused_process_is_replaced_after_a_timeout(
    env: VirtualEnvironment, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(venv_exec, "CALL_TIMEOUT", 0.5)
    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        with pytest.raises(RuntimeError, match=r"timed out after 0\.5 s"):
            asyncio.run(env.run(venv_callbacks.slow_callback))

        assert asyncio.run(env.run(venv_callbacks.process_id)) != process_id


_MEMORY_REPORT = (
    r"made {calls} calls, its memory went from [\d.]+ MiB after the first"
    r" to [\d.]+ MiB after the last"
)


def _venv_exec_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == venv_exec.__name__]


def test_reused_process_is_restarted_once_its_memory_grew_too_much(
    env: VirtualEnvironment,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(venv_exec, "MAX_MEMORY_GROWTH", 64 * 2**20)
    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        asyncio.run(env.run(venv_callbacks.keep_memory, args={"size": 32 * 2**20}))
        assert asyncio.run(env.run(venv_callbacks.process_id)) == process_id

        # Grown by 80 MiB since the first call
        asyncio.run(env.run(venv_callbacks.keep_memory, args={"size": 48 * 2**20}))
        with pytest.raises(ProcessLookupError):
            os.kill(process_id, 0)
        assert asyncio.run(env.run(venv_callbacks.process_id)) != process_id

    [warning] = _venv_exec_messages(caplog)
    assert re.fullmatch(
        "Restarting the venv subprocess, as its memory grew by more than 64 MiB: it "
        + _MEMORY_REPORT.format(calls=4),
        warning,
    )


def test_memory_of_a_reused_process_is_reported_at_the_end(
    env: VirtualEnvironment, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=venv_exec.__name__)
    asyncio.run(env.run(venv_callbacks.process_id))
    with env.reuse_venv():
        asyncio.run(env.run(venv_callbacks.process_id))
        asyncio.run(env.run(venv_callbacks.process_id))

    [report] = _venv_exec_messages(caplog)
    assert re.fullmatch("Venv subprocess " + _MEMORY_REPORT.format(calls=2), report)


def test_call_waiting_for_a_process_that_restarts_is_made_in_the_new_one(
    env: VirtualEnvironment, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(venv_exec, "MAX_MEMORY_GROWTH", 64 * 2**20)
    started = tmp_path / "started"

    async def call_while_the_process_restarts() -> int:
        leak = asyncio.create_task(
            env.run(
                venv_callbacks.announced_memory_leak,
                args={"started": str(started), "size": 96 * 2**20},
            )
        )
        assert await asyncio.to_thread(_wait_for, started) == process_id
        # Waits for the process until the leaking call restarts it
        waiting_call = await env.run(venv_callbacks.process_id)
        await leak
        return waiting_call

    with env.reuse_venv():
        process_id = asyncio.run(env.run(venv_callbacks.process_id))
        assert asyncio.run(call_while_the_process_restarts()) != process_id


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_return_value_larger_than_the_pipe_buffer_is_transferred(
    env: VirtualEnvironment, *, reuse_venv: bool
) -> None:
    size = 2**21
    with env.reuse_venv() if reuse_venv else nullcontext():
        result = asyncio.run(
            env.run(venv_callbacks.large_instructions, args={"size": size})
        )

    assert result == venv_callbacks.large_instructions(size)


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_output_of_the_interpreter_startup_is_not_taken_for_a_response(
    *, reuse_venv: bool
) -> None:
    with TemporaryDirectory() as temp_dir:
        venv.EnvBuilder().create(temp_dir)
        (site_packages,) = Path(temp_dir).glob("lib/python*/site-packages")
        (site_packages / "banner.pth").write_text(
            "import sys; print('banner!!', flush=True)\n"
        )
        env = VirtualEnvironment(temp_dir)

        with env.reuse_venv() if reuse_venv else nullcontext():
            first = asyncio.run(env.run(venv_callbacks.process_id))
            second = asyncio.run(env.run(venv_callbacks.process_id))

    assert (first == second) is reuse_venv


def _start_announced_slow_call(
    env: VirtualEnvironment, started: Path
) -> "asyncio.Task[None]":
    return asyncio.create_task(
        env.run(venv_callbacks.announced_slow_callback, args={"started": str(started)})
    )


def _wait_for(started: Path) -> int:
    """Wait for an announced callback of `venv_callbacks` to start, return its process."""
    deadline = time.monotonic() + 30
    while not started.exists():
        assert time.monotonic() < deadline, "the call did not start"
        time.sleep(0.01)
    return int(started.read_text())


def _venv_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith("venv")]


def test_calls_do_not_take_threads_of_the_default_executor(
    env: VirtualEnvironment,
) -> None:
    async def call_while_the_default_executor_is_busy() -> int:
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        occupied, release = asyncio.Event(), threading.Event()

        def occupy() -> None:
            loop.call_soon_threadsafe(occupied.set)
            release.wait()

        busy = asyncio.create_task(asyncio.to_thread(occupy))
        await occupied.wait()
        try:
            return await asyncio.wait_for(
                env.run(venv_callbacks.process_id), timeout=10
            )
        finally:
            release.set()
            await busy

    assert isinstance(asyncio.run(call_while_the_default_executor_is_busy()), int)


@pytest.mark.parametrize("reuse_venv", [False, True])
def test_shutdown_stops_the_running_calls_and_their_threads(
    env: VirtualEnvironment, tmp_path: Path, *, reuse_venv: bool
) -> None:
    started = tmp_path / "started"
    errors: list[BaseException] = []

    def call() -> None:
        with env.reuse_venv() if reuse_venv else nullcontext():
            try:
                asyncio.run(
                    env.run(
                        venv_callbacks.announced_slow_callback,
                        args={"started": str(started)},
                    )
                )
            except BaseException as e:
                errors.append(e)

    caller = threading.Thread(target=call)
    caller.start()
    process_id = _wait_for(started)
    start = time.monotonic()
    venv_exec.shutdown()
    caller.join()

    assert time.monotonic() - start < venv_callbacks.SLOW_CALLBACK_SECONDS / 2
    assert not _venv_threads()
    (error,) = errors
    assert isinstance(error, RuntimeError)
    assert "SIGKILL" in str(error)
    with pytest.raises(ProcessLookupError):
        os.kill(process_id, 0)
    # Later calls start new threads
    assert isinstance(asyncio.run(env.run(venv_callbacks.process_id)), int)


def test_shutdown_stops_a_call_of_a_cancelled_task(
    env: VirtualEnvironment, tmp_path: Path
) -> None:
    """Like the API server's tasks, which its shutdown cancels before the exit."""
    started = tmp_path / "started"

    async def cancel_a_running_call() -> None:
        task = _start_announced_slow_call(env, started)
        await asyncio.to_thread(_wait_for, started)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    asyncio.run(cancel_a_running_call())
    assert _venv_threads()
    start = time.monotonic()
    venv_exec.shutdown()

    assert time.monotonic() - start < venv_callbacks.SLOW_CALLBACK_SECONDS / 2
    assert not _venv_threads()


def test_end_of_reuse_stops_a_call_its_caller_gave_up_on(
    env: VirtualEnvironment, tmp_path: Path
) -> None:
    """Like the pre-processing worker, interrupted while it waits for a call."""
    started = tmp_path / "started"
    process_ids: list[int] = []

    async def give_up_on_a_running_call() -> None:
        task = _start_announced_slow_call(env, started)
        process_ids.append(await asyncio.to_thread(_wait_for, started))
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    start = time.monotonic()
    with env.reuse_venv():
        asyncio.run(give_up_on_a_running_call())

    assert time.monotonic() - start < venv_callbacks.SLOW_CALLBACK_SECONDS / 2
    with pytest.raises(ProcessLookupError):
        os.kill(process_ids[0], 0)


def _call_in_child(
    env: VirtualEnvironment, results: "multiprocessing.Queue[int]"
) -> None:
    results.put(asyncio.run(env.run(venv_callbacks.process_id)))


def test_forked_process_makes_its_calls_in_threads_of_its_own(
    env: VirtualEnvironment,
) -> None:
    """Like the pre-processing workers, forked from the API server."""
    # Starts the threads of this process
    parent_call = asyncio.run(env.run(venv_callbacks.process_id))
    context = multiprocessing.get_context("fork")
    results: multiprocessing.Queue[int] = context.Queue()
    with warnings.catch_warnings():
        # Of forking a process with threads
        warnings.simplefilter("ignore", DeprecationWarning)
        child = context.Process(target=_call_in_child, args=(env, results))
        child.start()
    try:
        child_call = results.get(timeout=30)
    finally:
        child.join(timeout=10)
        if child.is_alive():
            child.kill()

    assert child.exitcode == 0
    assert isinstance(child_call, int)
    assert child_call != parent_call
