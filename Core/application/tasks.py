from Core.application.diagnostics import diagnostic
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from threading import Condition, RLock
from time import monotonic
from typing import Callable
from uuid import uuid4
from traceback import format_exc
from math import isfinite, nextafter
from Core.configuration.settings import CORE_FILE_TASK_WORKERS

from Core.application.contracts import Cancelled, CoreError, CoreEvent, TaskSnapshot, TaskStage
from Core.application.router import AppManager, EventManager
from Core.application.retry_policy import retry_limit, transient_error
from Core.application.settings import CoreConfig


class Cancellation:
    def __init__(self) -> None:
        self._condition = Condition()
        self._cancelled = False
        self._paused = False

    def cancel(self) -> None:
        with self._condition:
            self._cancelled = True
            self._condition.notify_all()

    def pause(self) -> None:
        with self._condition:
            self._paused = True
            self._condition.notify_all()

    def resume(self) -> None:
        with self._condition:
            self._paused = False
            self._condition.notify_all()

    def is_paused(self) -> bool:
        with self._condition:
            return self._paused

    def check_cancelled(self) -> None:
        with self._condition:
            if self._cancelled:
                raise Cancelled(diagnostic('tasks.task.cancelled'))

    def check(self) -> None:
        with self._condition:
            while self._paused and not self._cancelled:
                self._condition.wait()
            if self._cancelled:
                raise Cancelled(diagnostic('tasks.task.cancelled'))

    def wait(self, seconds: float) -> None:
        remaining = max(0.0, seconds)
        with self._condition:
            while True:
                if self._cancelled:
                    raise Cancelled(diagnostic('tasks.task.cancelled'))
                if self._paused:
                    self._condition.wait()
                    continue
                if remaining <= 0:
                    return
                start = monotonic()
                self._condition.wait(remaining)
                remaining -= monotonic() - start


@dataclass(frozen=True)
class TaskOperation:
    run: Callable[[str, Cancellation], object]
    dependencies: tuple[str, ...]
    stages: tuple[TaskStage, ...]
    queue: str


class TaskManager:
    def __init__(self, app: AppManager, workers: int) -> None:
        self._app = app
        self._executors = {
            'background': ThreadPoolExecutor(max_workers=workers, thread_name_prefix='launcher-core'),
            'files': ThreadPoolExecutor(max_workers=CORE_FILE_TASK_WORKERS, thread_name_prefix='launcher-files'),
        }
        self._lock = RLock()
        self._snapshots: dict[str, TaskSnapshot] = {}
        self._tokens: dict[str, Cancellation] = {}
        self._futures: dict[str, Future[object]] = {}
        self._started: set[str] = set()
        self._pending: dict[str, DependentTask] = {}
        self._operations: dict[str, TaskOperation] = {}
        self._closed = False

    def submit(self, title: str, operation: Callable[[str, Cancellation], object], dependencies: tuple[str, ...] = (), stages: tuple[TaskStage, ...] = (), *, queue: str = 'background', retryable: bool = False) -> str:
        if not isinstance(stages, tuple) or any(not isinstance(stage, TaskStage) for stage in stages) or len({stage.key for stage in stages}) != len(stages) or not isfinite(sum(stage.weight for stage in stages)):
            raise ValueError(diagnostic('tasks.task.stages.must.be.an.immutable'))
        retries = retry_limit(self._app) if retryable else 0
        with self._lock:
            if self._closed:
                raise RuntimeError(diagnostic('tasks.task.manager.is.closed'))
            if queue not in self._executors:
                raise ValueError(diagnostic('tasks.invalid.queue', queue))
            prerequisites = tuple(self._futures[key] for key in dict.fromkeys(dependencies))
            task_id = uuid4().hex
            token = Cancellation()
            self._tokens[task_id] = token
            self._snapshots[task_id] = TaskSnapshot(task_id, title, "queued", stages=stages, can_retry=retryable, retry_limit=retries)
            if retryable:
                self._operations[task_id] = TaskOperation(operation, tuple(dict.fromkeys(dependencies)), stages, queue)
            self._publish(self._snapshots[task_id])
            if prerequisites:
                future: Future[object] = Future()
                pending = DependentTask(self, task_id, token, operation, prerequisites, future, queue)
                self._futures[task_id] = future
                self._pending[task_id] = pending
            else:
                self._futures[task_id] = self._executors[queue].submit(self._run, task_id, token, operation)
        if prerequisites:
            pending.watch()
        return task_id

    def start_dependent(self, task_id: str, token: Cancellation, operation: Callable[[str, Cancellation], object], queue: str) -> Future[object]:
        with self._lock:
            if self._closed:
                raise Cancelled(diagnostic('tasks.task.manager.is.closed'))
            return self._executors[queue].submit(self._run, task_id, token, operation)

    def _run(self, task_id: str, token: Cancellation, operation: Callable[[str, Cancellation], object]) -> object:
        try:
            with self._lock:
                self._started.add(task_id)
                if self._snapshots[task_id].state == "queued":
                    self.update(task_id, "running")
            self._app.log("Task started: " + task_id + " " + self._snapshots[task_id].title, "DEBUG")
            retries = self._snapshots[task_id].retry_limit
            for attempt in range(retries + 1):
                token.check()
                try:
                    result = operation(task_id, token)
                    break
                except Exception as error:
                    if isinstance(error, Cancelled) or not self._snapshots[task_id].can_retry or attempt == retries or not transient_error(error):
                        raise
                    with self._lock:
                        old = self._snapshots[task_id]
                        self._snapshots[task_id] = replace(old, retry_count=attempt + 1)
                        self.update(task_id, 'paused' if token.is_paused() else 'retrying', error=str(error))
                    self._app.log_error(format_exc())
                    token.wait(self._app.get('config', CoreConfig).retry_delay * (2 ** attempt))
                    with self._lock:
                        self._reset(task_id, 'paused' if token.is_paused() else 'running', attempt + 1)
            self.update(task_id, "completed")
            self._app.log("Task completed: " + task_id, "DEBUG")
            return result
        except Cancelled:
            self.update(task_id, "cancelled")
            raise
        except Exception as error:
            self.update(task_id, "failed", error=str(error))
            self._app.log_error(format_exc())
            raise

    def _reset(self, task_id: str, state: str, retry_count: int = 0) -> None:
        old = self._snapshots[task_id]
        snapshot = TaskSnapshot(task_id, old.title, state, stages=self._operations[task_id].stages, can_retry=True, retry_count=retry_count, retry_limit=old.retry_limit)
        self._snapshots[task_id] = snapshot
        self._publish(snapshot)

    def retry(self, task_id: str) -> bool:
        return self._retry(task_id, retry_limit(self._app))

    def _retry(self, task_id: str, retries: int) -> bool:
        with self._lock:
            old = self._snapshots.get(task_id)
            future = self._futures.get(task_id)
            if self._closed or old is None or old.state not in ('failed', 'cancelled') or task_id not in self._operations or future is None or not future.done():
                return False
            operation = self._operations[task_id]
            for key in operation.dependencies:
                prerequisite = self._futures.get(key)
                snapshot = self._snapshots.get(key)
                if prerequisite is None or snapshot is None:
                    return False
                if snapshot.state in ('failed', 'cancelled') and not self._retry(key, retries):
                    return False
            token = Cancellation()
            self._tokens[task_id] = token
            self._started.discard(task_id)
            self._pending.pop(task_id, None)
            self._snapshots[task_id] = replace(old, retry_limit=retries)
            self._reset(task_id, 'queued')
            prerequisites = tuple(self._futures[key] for key in operation.dependencies)
            if prerequisites:
                result: Future[object] = Future()
                pending = DependentTask(self, task_id, token, operation.run, prerequisites, result, operation.queue)
                self._futures[task_id] = result
                self._pending[task_id] = pending
            else:
                self._futures[task_id] = self._executors[operation.queue].submit(self._run, task_id, token, operation.run)
        if prerequisites:
            pending.watch()
        return True

    def _publish(self, snapshot: TaskSnapshot) -> None:
        self._app.get("events", EventManager).publish(CoreEvent("task", snapshot))

    def update(self, task_id: str, state: str | None = None, completed_bytes: int | None = None, total_bytes: int | None = None, error: str = "") -> None:
        with self._lock:
            old = self._snapshots[task_id]
            snapshot = replace(old, state=state or old.state, completed_bytes=old.completed_bytes if completed_bytes is None else completed_bytes, total_bytes=old.total_bytes if total_bytes is None else total_bytes, error=error)
            if snapshot.state != 'running':
                snapshot = replace(snapshot, bytes_per_second=0.0)
            if snapshot.state == "completed":
                snapshot = replace(snapshot, progress=1.0, stage_progress=1.0)
            self._snapshots[task_id] = snapshot
            self._publish(snapshot)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            if self._snapshots[task_id].state in ("completed", "cancelled", "failed", "cancelling"):
                return False
            self._tokens[task_id].cancel()
            self.update(task_id, "cancelling")
            pending = self._pending.get(task_id)
        if pending:
            pending.cancel()
        return True

    def start_stage(self, task_id: str, key: str) -> None:
        with self._lock:
            old = self._snapshots[task_id]
            index = old.stage_index + 1
            if index >= len(old.stages) or old.stages[index].key != key:
                raise ValueError(diagnostic('tasks.task.stages.must.execute.in.their'))
            snapshot = replace(old, stage_index=index, stage_step=0, stage_steps=1, completed_bytes=0, total_bytes=None, stage_progress=None, bytes_per_second=0.0)
            snapshot = replace(snapshot, progress=max(old.progress or 0.0, self._overall(snapshot, None) or 0.0))
            self._snapshots[task_id] = snapshot
            self._publish(snapshot)

    def stage_step(self, task_id: str, index: int, count: int) -> None:
        with self._lock:
            old = self._snapshots[task_id]
            if old.stage_index < 0 or type(index) is not int or type(count) is not int or count < 1 or not 0 <= index < count or index < old.stage_step or count != old.stage_steps and (old.stage_step > 0 or old.progress is not None and old.progress > (self._overall(old, None) or 0.0)):
                raise ValueError(diagnostic('tasks.invalid.task.stage.step'))
            snapshot = replace(old, stage_step=index, stage_steps=count, completed_bytes=0, total_bytes=None, stage_progress=None, bytes_per_second=0.0)
            snapshot = replace(snapshot, progress=max(old.progress or 0.0, self._overall(snapshot, None) or 0.0))
            self._snapshots[task_id] = snapshot
            self._publish(snapshot)

    def expand_stage(self, task_id: str, key: str, stages: tuple[TaskStage, ...]) -> None:
        if not isinstance(stages, tuple) or not stages or any(not isinstance(stage, TaskStage) for stage in stages) or not isfinite(sum(stage.weight for stage in stages)):
            raise ValueError(diagnostic('tasks.invalid.expanded.task.stages'))
        with self._lock:
            old = self._snapshots[task_id]
            if old.stage_index < 0 or old.stages[old.stage_index].key != key or old.stage_step or old.completed_bytes or old.progress is not None and old.progress > (self._overall(old, None) or 0.0):
                raise ValueError(diagnostic('tasks.a.task.stage.can.only.expand'))
            weight = old.stages[old.stage_index].weight
            total = sum(stage.weight for stage in stages)
            expanded = tuple(replace(stage, weight=weight * (stage.weight / total)) for stage in stages)
            plan = old.stages[:old.stage_index] + expanded + old.stages[old.stage_index + 1:]
            if len({stage.key for stage in plan}) != len(plan):
                raise ValueError(diagnostic('tasks.expanded.task.stage.keys.must.be'))
            snapshot = replace(old, stages=plan, stage_index=old.stage_index - 1, stage_steps=1, stage_step=0, stage_progress=None)
            self._snapshots[task_id] = snapshot
            self._publish(snapshot)

    @staticmethod
    def _overall(snapshot: TaskSnapshot, fraction: float | None) -> float | None:
        if not snapshot.stages or snapshot.stage_index < 0:
            return fraction
        completed = sum(stage.weight for stage in snapshot.stages[:snapshot.stage_index])
        stage = snapshot.stages[snapshot.stage_index]
        local = (snapshot.stage_step + (fraction or 0.0)) / snapshot.stage_steps
        return min(nextafter(1.0, 0.0), (completed + stage.weight * local) / sum(stage.weight for stage in snapshot.stages))

    def progress(self, task_id: str, completed_bytes: int, total_bytes: int | None, fraction: float | None = None, bytes_per_second: float = 0.0) -> None:
        if completed_bytes < 0 or total_bytes is not None and total_bytes < 0 or fraction is not None and (not isfinite(fraction) or not 0 <= fraction <= 1) or not isfinite(bytes_per_second) or bytes_per_second < 0:
            raise ValueError(diagnostic('tasks.invalid.task.progress'))
        with self._lock:
            old = self._snapshots[task_id]
            local = fraction if fraction is not None else min(1.0, completed_bytes / total_bytes) if total_bytes else None
            snapshot = replace(old, completed_bytes=completed_bytes, total_bytes=total_bytes, stage_progress=local, bytes_per_second=bytes_per_second if old.state == 'running' else 0.0)
            overall = self._overall(snapshot, local)
            if overall is not None:
                overall = min(nextafter(1.0, 0.0), max(old.progress or 0.0, overall))
            snapshot = replace(snapshot, progress=overall if overall is not None else old.progress)
            self._snapshots[task_id] = snapshot
            self._publish(snapshot)

    def pause(self, task_id: str) -> bool:
        with self._lock:
            if self._snapshots[task_id].state not in ("queued", "running", "retrying"):
                return False
            self._tokens[task_id].pause()
            self.update(task_id, "paused")
            return True

    def resume(self, task_id: str) -> bool:
        with self._lock:
            if self._snapshots[task_id].state != "paused":
                return False
            self._tokens[task_id].resume()
            self.update(task_id, "running" if task_id in self._started else "queued")
            return True

    def wait(self, task_id: str, timeout: float | None = None) -> object:
        with self._lock:
            future = self._futures[task_id]
        return future.result(timeout)

    def snapshots(self) -> tuple[TaskSnapshot, ...]:
        with self._lock:
            return tuple(self._snapshots.values())

    def forget(self, task_id: str) -> bool:
        with self._lock:
            future = self._futures.get(task_id)
            if future is None or not future.done():
                return False
            del self._futures[task_id]
            self._snapshots.pop(task_id, None)
            self._tokens.pop(task_id, None)
            self._started.discard(task_id)
            self._pending.pop(task_id, None)
            self._operations.pop(task_id, None)
            return True

    def release(self, task_id: str) -> None:
        with self._lock:
            future = self._futures.get(task_id)
            if future is not None:
                future.add_done_callback(TaskRelease(self, task_id).finished)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            tokens = tuple(self._tokens.values())
            pending = tuple(self._pending.values())
        for token in tokens:
            token.cancel()
        for task in pending:
            task.cancel()
        for executor in self._executors.values():
            executor.shutdown(wait=True)


class TaskRelease:
    def __init__(self, manager: TaskManager, task_id: str) -> None:
        self._manager = manager
        self._task_id = task_id

    def finished(self, future: Future[object]) -> None:
        self._manager.forget(self._task_id)


class DependentTask:
    def __init__(self, manager: TaskManager, task_id: str, token: Cancellation, operation: Callable[[str, Cancellation], object], dependencies: tuple[Future[object], ...], result: Future[object], queue: str) -> None:
        self._manager = manager
        self._task_id = task_id
        self._token = token
        self._operation = operation
        self._dependencies = dependencies
        self._result = result
        self._lock = RLock()
        self._scheduled = False
        self._queue = queue

    def watch(self) -> None:
        for dependency in self._dependencies:
            dependency.add_done_callback(self.ready)

    def ready(self, dependency: Future[object]) -> None:
        with self._lock:
            if self._scheduled or self._result.done() or not all(item.done() for item in self._dependencies):
                return
            try:
                self._token.check_cancelled()
                for prerequisite in self._dependencies:
                    prerequisite.result()
                worker = self._manager.start_dependent(self._task_id, self._token, self._operation, self._queue)
                self._scheduled = True
                worker.add_done_callback(self.completed)
            except Cancelled as error:
                self._fail(error)
            except Exception as error:
                self._fail(CoreError("Required download failed: " + str(error)))

    def completed(self, worker: Future[object]) -> None:
        with self._lock:
            try:
                self._result.set_result(worker.result())
            except Exception as error:
                self._result.set_exception(error)

    def _fail(self, error: Exception) -> None:
        self._manager.update(self._task_id, "cancelled" if isinstance(error, Cancelled) else "failed", error=str(error))
        self._result.set_exception(error)

    def cancel(self) -> None:
        with self._lock:
            if not self._scheduled and not self._result.done():
                self._fail(Cancelled("Task cancelled"))
