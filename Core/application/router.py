from Core.application.diagnostics import diagnostic
from Core.configuration.settings import BACKEND_EVENT_DRAIN_LIMIT
from contextlib import contextmanager
from collections.abc import Iterator
from queue import Empty, SimpleQueue
from threading import RLock
from types import ModuleType
from typing import Callable, Protocol, TypeVar, runtime_checkable
from time import monotonic
from dataclasses import dataclass

from Core.application.contracts import CoreEvent, TaskSnapshot, DownloadItemProgress


@dataclass(slots=True)
class _PendingEvent:
    event: CoreEvent
    key: tuple | None
    phase: object


class Closable(Protocol):
    def close(self) -> None: ...


@runtime_checkable
class LogSink(Protocol):
    def write(self, message: str, level: str = "INFO") -> None: ...


T = TypeVar("T")


class AppManager:
    def __init__(self) -> None:
        self._managers: dict[str, object] = {}
        self._lock = RLock()

    def register(self, name: str, manager: object) -> None:
        with self._lock:
            if name in self._managers:
                raise ValueError(diagnostic('router.manager.already.registered', name))
            self._managers[name] = manager

    def get(self, name: str, expected_type: type[T]) -> T:
        with self._lock:
            value = self._managers[name]
        if not isinstance(value, expected_type):
            raise TypeError(diagnostic('router.invalid.manager.contract', name))
        return value

    def log_error(self, message: str) -> None:
        self.log(message, "ERROR")

    def log(self, message: str, level: str) -> None:
        with self._lock:
            logger = self._managers.get("logs")
        if isinstance(logger, LogSink):
            try:
                logger.write(message, level)
            except OSError:
                pass


class EventManager:
    def __init__(self) -> None:
        self._queue: SimpleQueue[_PendingEvent] = SimpleQueue()
        self._progress: dict[tuple, _PendingEvent] = {}
        self._listeners: dict[str, list[Callable[[CoreEvent], None]]] = {}
        self._immediate: dict[str, list[Callable[[CoreEvent], None]]] = {}
        self._lock = RLock()

    def publish(self, event: CoreEvent) -> None:
        with self._lock:
            payload = event.payload
            key, phase = None, None
            if isinstance(payload, TaskSnapshot):
                key, phase = (event.topic, payload.task_id), (payload.state, payload.stage_index)
            elif isinstance(payload, DownloadItemProgress):
                key, phase = (event.topic, payload.task_id, payload.key), payload.verified
            pending = self._progress.get(key) if key is not None else None
            if pending is not None and pending.phase == phase:
                pending.event = event
            else:
                pending = _PendingEvent(event, key, phase)
                self._queue.put(pending)
                if key is not None:
                    self._progress[key] = pending
            listeners = tuple(self._immediate.get(event.topic, ()))
        for listener in listeners:
            listener(event)

    def subscribe(self, topic: str, listener: Callable[[CoreEvent], None], deferred: bool = True) -> None:
        owner = getattr(listener, "__self__", None)
        if owner is None or isinstance(owner, ModuleType):
            raise TypeError(diagnostic('router.event.subscriptions.require.bound.instance.methods'))
        with self._lock:
            target = self._listeners if deferred else self._immediate
            target.setdefault(topic, []).append(listener)

    def unsubscribe(self, topic: str, listener: Callable[[CoreEvent], None]) -> None:
        with self._lock:
            for target in (self._listeners, self._immediate):
                entries = target.get(topic, [])
                if listener in entries:
                    entries.remove(listener)

    def drain(self, limit: int = BACKEND_EVENT_DRAIN_LIMIT, maximum_ms: float | None = None) -> tuple[CoreEvent, ...]:
        events: list[CoreEvent] = []
        deadline = monotonic() + maximum_ms / 1000 if maximum_ms is not None else None
        for _ in range(limit):
            with self._lock:
                try:
                    pending = self._queue.get_nowait()
                except Empty:
                    break
                if pending.key is not None and self._progress.get(pending.key) is pending:
                    del self._progress[pending.key]
                event = pending.event
                listeners = tuple(self._listeners.get(event.topic, ()))
            events.append(event)
            for listener in listeners:
                listener(event)
            if deadline is not None and monotonic() >= deadline:
                break
        return tuple(events)

    def has_pending(self) -> bool:
        return not self._queue.empty()

    def close(self) -> None:
        with self._lock:
            self._listeners.clear()
            self._immediate.clear()
            self._progress.clear()


class CancellationCheck(Protocol):
    def check(self) -> None: ...


class AccessManager:
    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._lock = RLock()
        self._resources: dict[str, tuple[RLock, int]] = {}

    @contextmanager
    def access(self, resource: str, cancellation: CancellationCheck) -> Iterator[None]:
        key = resource.casefold()
        with self._lock:
            entry = self._resources.get(key)
            lock, users = entry if entry is not None else (RLock(), 0)
            self._resources[key] = (lock, users + 1)
        acquired = False
        try:
            cancellation.check()
            while not lock.acquire(timeout=self._interval):
                cancellation.check()
            acquired = True
            cancellation.check()
            yield
        finally:
            if acquired:
                lock.release()
            with self._lock:
                _, users = self._resources[key]
                if users == 1:
                    del self._resources[key]
                else:
                    self._resources[key] = (lock, users - 1)

    def count(self) -> int:
        with self._lock:
            return len(self._resources)

    def close(self) -> None:
        with self._lock:
            self._resources.clear()
