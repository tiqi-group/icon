from __future__ import annotations

import collections
import contextlib
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from icon.server.hardware_processing.task import HardwareProcessingTask


class Arbiter:
    """The pre-processing workers' task queues, which the hardware worker pulls from.

    Hosted by the :class:`~icon.server.shared_resource_manager.SharedResourceManager`.
    Every pre-processing worker has its own queue of prepared tasks, in the order it put
    them, so it can take them back (e.g. when their parameters went stale) or hold them
    (while the job is paused). The hardware worker pulls the next task of the queue
    whose task goes first: lower priority values first, then the task created first.
    """

    def __init__(self) -> None:
        self._changed = threading.Condition()
        """Guards the task queues; notified whenever one changes."""
        self._tasks: collections.defaultdict[
            int, collections.deque[HardwareProcessingTask]
        ] = collections.defaultdict(collections.deque)
        self._held: set[int] = set()
        self._finished: collections.Counter[int] = collections.Counter()

    def put(self, worker: int, task: HardwareProcessingTask) -> None:
        with self._changed:
            self._tasks[worker].append(task)
            self._changed.notify_all()

    def wait_for_space(self, worker: int, size: int, timeout: float) -> bool:
        """Wait until a worker's task queue holds fewer than ``size`` tasks.

        Returns:
            False if it still doesn't after ``timeout`` seconds.
        """
        with self._changed:
            return self._changed.wait_for(
                lambda: len(self._tasks[worker]) < size, timeout
            )

    def take_back(self, worker: int, run_id: int) -> list[HardwareProcessingTask]:
        """Take a job run's tasks out of a worker's queue, keeping the order of the others.

        Returns:
            The tasks taken out, in order.
        """
        with self._changed:
            tasks = self._tasks[worker]
            taken = [t for t in tasks if t.pre_processing_task.job_run.id == run_id]
            self._tasks[worker] = collections.deque(
                t for t in tasks if t.pre_processing_task.job_run.id != run_id
            )
            self._changed.notify_all()
            return taken

    def set_held(self, worker: int, *, held: bool) -> None:
        """Hand over none of a worker's tasks while it is held."""
        with self._changed:
            if held:
                self._held.add(worker)
            else:
                self._held.discard(worker)
            self._changed.notify_all()

    def pull(self) -> HardwareProcessingTask:
        """Take out the task that goes first, waiting for one if there is none."""
        with self._changed:
            while (worker := self._next_worker()) is None:
                self._changed.wait()
            self._changed.notify_all()
            return self._tasks[worker].popleft()

    def pop(self, worker: int) -> HardwareProcessingTask | None:
        """Take out a worker's next task, or None if it has none or is held."""
        with self._changed:
            if worker in self._held or not self._tasks[worker]:
                return None
            self._changed.notify_all()
            return self._tasks[worker].popleft()

    def mark_finished(self, run_id: int) -> None:
        with self._changed:
            self._finished[run_id] += 1

    def finished(self, run_id: int) -> int:
        """Number of the job run's tasks the hardware worker finished."""
        with self._changed:
            return self._finished[run_id]

    def _next_worker(self) -> int | None:
        ready = [
            (tasks[0].priority, tasks[0].created, worker)
            for worker, tasks in self._tasks.items()
            if tasks and worker not in self._held
        ]
        return min(ready)[2] if ready else None


class TaskQueue:
    """A pre-processing worker's task queue in the :class:`Arbiter`."""

    def __init__(self, arbiter: Arbiter, worker: int, size: int) -> None:
        self._arbiter = arbiter
        self._worker = worker
        self._size = size

    def put(self, task: HardwareProcessingTask) -> None:
        self._arbiter.put(self._worker, task)

    def wait_for_space(self, timeout: float) -> bool:
        """Wait until there is room for another task.

        Returns:
            False if there is still no room after ``timeout`` seconds.
        """
        return self._arbiter.wait_for_space(self._worker, self._size, timeout)

    def take_back(self, run_id: int) -> list[HardwareProcessingTask]:
        """Take out the tasks of a job run, keeping the order of the others.

        Returns:
            The tasks taken out, in order.
        """
        return self._arbiter.take_back(self._worker, run_id)

    @contextlib.contextmanager
    def held(self) -> Generator[None]:
        """Hand over no tasks while in this context."""
        self._arbiter.set_held(self._worker, held=True)
        try:
            yield
        finally:
            self._arbiter.set_held(self._worker, held=False)

    def pop(self) -> HardwareProcessingTask | None:
        """Take out the next task, or None if there is none or the queue is held."""
        return self._arbiter.pop(self._worker)

    def finished(self, run_id: int) -> int:
        """Number of the job run's tasks the hardware worker finished."""
        return self._arbiter.finished(run_id)
