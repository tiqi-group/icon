from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, cast

from icon.server.pre_processing.arbiter import Arbiter, TaskQueue
from icon.server.shared_resource_manager import SharedResourceManager

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
RUN_ID = 1
OTHER_RUN_ID = 99
QUEUE_SIZE = 2


@dataclasses.dataclass
class _Task:
    name: str
    priority: int = 0
    seconds: float = 0.0
    """Seconds after T0 it was created."""
    run_id: int = RUN_ID

    @property
    def created(self) -> datetime:
        return T0 + timedelta(seconds=self.seconds)

    @property
    def pre_processing_task(self) -> Any:
        return SimpleNamespace(job_run=SimpleNamespace(id=self.run_id))


def _names(tasks: list[Any]) -> list[str]:
    return [task.name for task in tasks]


def _arbiter_and_queues(n: int = 2) -> tuple[Arbiter, list[TaskQueue]]:
    arbiter = Arbiter()
    return arbiter, [TaskQueue(arbiter, i, size=QUEUE_SIZE) for i in range(n)]


def _pull(arbiter: Arbiter) -> str:
    return cast("Any", arbiter.pull()).name


def _pull_ready(arbiter: Arbiter) -> Any | None:
    """Pull a task as the hardware worker does, or None instead of waiting for one."""
    return arbiter.pull() if arbiter._next_worker() is not None else None


def _put(task_queue: TaskQueue, *tasks: _Task) -> None:
    for task in tasks:
        task_queue.put(cast("Any", task))


def test_task_queue_takes_back_a_runs_tasks() -> None:
    arbiter, (task_queue,) = _arbiter_and_queues(1)
    _put(
        task_queue,
        _Task("a", run_id=OTHER_RUN_ID),
        _Task("b"),
        _Task("c", run_id=OTHER_RUN_ID),
        _Task("d"),
    )

    assert _names(task_queue.take_back(RUN_ID)) == ["b", "d"]
    assert [_pull(arbiter), _pull(arbiter)] == ["a", "c"]
    assert _pull_ready(arbiter) is None


def test_task_queue_waits_for_space() -> None:
    arbiter, (task_queue,) = _arbiter_and_queues(1)
    _put(task_queue, _Task("a"), _Task("b"))
    assert not task_queue.wait_for_space(timeout=0.01)

    threading.Timer(0.01, arbiter.pull).start()
    assert task_queue.wait_for_space(timeout=5)


def test_arbiter_picks_by_priority_then_creation_time() -> None:
    arbiter, (queue_a, queue_b) = _arbiter_and_queues()
    _put(queue_a, _Task("a0", 5, 0), _Task("a1", 5, 3))
    _put(queue_b, _Task("b0", 5, 1), _Task("b1", 0, 2))

    assert [_pull(arbiter) for _ in range(4)] == ["a0", "b0", "b1", "a1"]


def test_arbiter_skips_the_task_queues_of_held_job_runs() -> None:
    arbiter, task_queues = _arbiter_and_queues()
    _put(task_queues[0], _Task("a0", 0), _Task("a1", 0, 3))
    _put(task_queues[1], _Task("b0", 5, 1, run_id=OTHER_RUN_ID))
    arbiter.hold(RUN_ID)

    assert _pull(arbiter) == "b0"
    assert _pull_ready(arbiter) is None

    arbiter.release(RUN_ID)
    assert [_pull(arbiter), _pull(arbiter)] == ["a0", "a1"]


def test_arbiter_hands_over_a_released_job_runs_task_to_a_waiting_pull() -> None:
    arbiter, (task_queue, _) = _arbiter_and_queues()
    arbiter.hold(RUN_ID)
    _put(task_queue, _Task("a0"))
    threading.Timer(0.01, arbiter.release, args=[RUN_ID]).start()

    assert _pull(arbiter) == "a0"


def test_arbiter_waits_for_a_task() -> None:
    arbiter, task_queues = _arbiter_and_queues()
    threading.Timer(0.01, _put, args=[task_queues[1], _Task("b0")]).start()

    assert _pull(arbiter) == "b0"


def test_arbiter_counts_finished_tasks_of_started_job_runs() -> None:
    """From zero, also if the job run's ID was used before."""
    arbiter, (task_queue, _) = _arbiter_and_queues()
    task_queue.start_run(RUN_ID)
    arbiter.mark_finished(RUN_ID)
    arbiter.mark_finished(RUN_ID)
    arbiter.mark_finished(OTHER_RUN_ID)

    assert task_queue.finished(RUN_ID) == 2  # noqa: PLR2004
    assert task_queue.finished(OTHER_RUN_ID) == 0

    task_queue.start_run(RUN_ID)
    assert task_queue.finished(RUN_ID) == 0


def test_ended_job_run_is_forgotten() -> None:
    """Its tasks left are dropped; its hold and count of finished tasks are forgotten.

    Also when the hardware worker finishes a task of the job run after it ended, e.g. of
    a cancelled one.
    """
    arbiter, (task_queue, _) = _arbiter_and_queues()
    task_queue.start_run(RUN_ID)
    arbiter.hold(RUN_ID)
    _put(task_queue, _Task("a0"), _Task("a1"))
    arbiter.mark_finished(RUN_ID)

    task_queue.end_run(RUN_ID)
    arbiter.mark_finished(RUN_ID)

    assert _pull_ready(arbiter) is None
    assert task_queue.finished(RUN_ID) == 0
    assert not arbiter._held
    assert not arbiter._finished


def test_through_the_shared_resource_manager() -> None:
    """As in the server, with the arbiter in the manager's process."""
    manager = SharedResourceManager()
    manager.start_srm()
    try:
        arbiter = manager.task_arbiter
        task_queue = TaskQueue(arbiter, 0, size=1)
        task_queue.start_run(RUN_ID)
        threading.Timer(0.01, _put, args=[task_queue, _Task("a0")]).start()

        assert _pull(arbiter) == "a0"
        arbiter.mark_finished(RUN_ID)
        assert task_queue.finished(RUN_ID) == 1
        arbiter.hold(RUN_ID)
        _put(task_queue, _Task("a1"))
        assert not task_queue.wait_for_space(timeout=0.01)
        assert _names(task_queue.take_back(RUN_ID)) == ["a1"]
        _put(task_queue, _Task("a2"))
        threading.Timer(0.01, arbiter.release, args=[RUN_ID]).start()
        assert _pull(arbiter) == "a2"
        task_queue.end_run(RUN_ID)
        assert task_queue.finished(RUN_ID) == 0
    finally:
        manager.shutdown()
