from Core.application.diagnostics import diagnostic
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from threading import RLock
from time import monotonic
from http.client import HTTPException

from Core.application.contracts import Artifact, Cancelled, CoreError, CoreEvent, DownloadBatch, DownloadItemProgress, HttpRequest, TaskStage
from Core.network.network import NetworkManager, RangeUnavailable, IncompleteResponse
from Core.application.router import AccessManager, AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager
from Core.application.tasks import Cancellation, TaskManager
from Core.application.retry_policy import DownloadRetriesExhausted, retry_limit


class DownloadManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config

    def submit(self, request: DownloadBatch) -> str:
        operation = DownloadOperation(self._app, request)
        return self._app.get("tasks", TaskManager).submit(request.title, operation.run, stages=(TaskStage("download"),), retryable=True)

    def pause(self, task_id: str) -> bool:
        return self._app.get("tasks", TaskManager).pause(task_id)

    def resume(self, task_id: str) -> bool:
        return self._app.get("tasks", TaskManager).resume(task_id)

    def cancel(self, task_id: str) -> bool:
        return self._app.get("tasks", TaskManager).cancel(task_id)

    def fetch(self, artifact: Artifact, cancellation: Cancellation, progress: "DownloadProgress | None" = None) -> None:
        self._validate(artifact)
        files = self._app.get("files", FileManager)
        canonical = str(files.path(artifact.relative_path)).casefold()
        with self._app.get("access", AccessManager).access("download:" + canonical, cancellation):
            cancellation.check()
            if files.cached(artifact, cancellation):
                if progress:
                    progress.set(artifact.relative_path, artifact.size if artifact.size is not None else files.size(artifact.relative_path))
                    progress.complete(artifact.relative_path)
                return
            network = self._app.get("network", NetworkManager)
            token, size = files.begin(artifact.relative_path), 0
            try:
                retries = retry_limit(self._app)
                for attempt in range(retries + 1):
                    cancellation.check()
                    try:
                        if progress:
                            progress.set(artifact.relative_path, size)
                        for chunk in network.stream(HttpRequest(artifact.url, size), cancellation):
                            size += len(chunk.data)
                            if artifact.size is not None and size > artifact.size:
                                raise CoreError(diagnostic('downloads.downloaded.file.exceeds.declared.size'))
                            files.append(token, chunk.data)
                            if progress:
                                progress.set(artifact.relative_path, size, len(chunk.data))
                        files.commit(token, artifact, cancellation, durable=False)
                        if progress:
                            progress.complete(artifact.relative_path)
                        return
                    except Cancelled:
                        raise
                    except Exception as error:
                        self._app.log(diagnostic('downloads.retry', artifact.relative_path, size, attempt + 1, retries + 1, error), 'WARNING')
                        if attempt == retries:
                            raise DownloadRetriesExhausted(str(error)) from error
                        resume = artifact.digests and isinstance(error, (OSError, HTTPException, IncompleteResponse)) and not isinstance(error, RangeUnavailable)
                        if not resume:
                            files.discard(token)
                            token, size = files.begin(artifact.relative_path), 0
                        if not isinstance(error, RangeUnavailable):
                            cancellation.wait(self._config.retry_delay * (2 ** attempt))
            finally:
                files.discard(token)

    def _validate(self, artifact: Artifact) -> None:
        if artifact.size is not None and artifact.size < 0:
            raise CoreError(diagnostic('downloads.artifact.size.cannot.be.negative'))
        lengths = {"sha1": 40, "sha256": 64, "sha512": 128}
        for digest in artifact.digests:
            if digest.algorithm not in lengths or len(digest.value) != lengths[digest.algorithm] or any(character not in "0123456789abcdefABCDEF" for character in digest.value):
                raise CoreError(diagnostic('downloads.invalid.integrity.digest'))

    def close(self) -> None:
        pass

    def execute(self, request: DownloadBatch, task_id: str, cancellation: Cancellation) -> tuple[str, ...]:
        return DownloadOperation(self._app, request).run(task_id, cancellation)


class DownloadProgress:
    def __init__(self, app: AppManager, task_id: str, request: DownloadBatch) -> None:
        self._app = app
        self._task_id = task_id
        self._sizes = {artifact.relative_path: 0 for artifact in request.artifacts}
        self._totals = {artifact.relative_path: artifact.size for artifact in request.artifacts}
        self._keys = dict(request.item_keys)
        self._published = {}
        config = app.get('config', CoreConfig)
        self._interval = config.download_item_interval
        self._progress_interval = config.download_progress_interval
        self._speed_window = config.download_speed_window
        self._completed_bytes = 0
        self._transferred = 0
        self._last_publish = monotonic()
        self._samples = deque([(self._last_publish, 0)])
        self._completed: set[str] = set()
        self._total = sum(artifact.size for artifact in request.artifacts if artifact.size is not None) if all(artifact.size is not None for artifact in request.artifacts) else None
        self._lock = RLock()
        self._app.get("tasks", TaskManager).progress(self._task_id, 0, self._total, 1.0 if not self._sizes else 0.0 if self._total is not None else None)

    def set(self, path: str, size: int, received_bytes: int = 0) -> None:
        with self._lock:
            previous = self._sizes[path]
            self._sizes[path] = size
            self._completed_bytes += size - previous
            self._transferred += received_bytes
            self._publish(False)
            self._publish_item(path, size == 0 or previous == 0)

    def complete(self, path: str) -> None:
        with self._lock:
            self._completed.add(path)
            self._publish(True)
            self._publish_item(path, True)

    def _publish_item(self, path: str, force: bool) -> None:
        if path not in self._keys:
            return
        now = monotonic()
        if force or now - self._published.get(path, 0) >= self._interval:
            self._published[path] = now
            self._app.get('events', EventManager).publish(CoreEvent('download.item', DownloadItemProgress(self._task_id, self._keys[path], self._sizes[path], self._totals[path], path in self._completed)))

    def _publish(self, completed_file: bool) -> None:
        now = monotonic()
        finished = len(self._completed) == len(self._sizes)
        if now - self._last_publish < self._progress_interval and not finished:
            return
        self._last_publish = now
        self._samples.append((now, self._transferred))
        while len(self._samples) > 2 and self._samples[1][0] <= now - self._speed_window:
            self._samples.popleft()
        began, transferred = self._samples[0]
        speed = (self._transferred - transferred) / (now - began) if now > began and not finished else 0.0
        fraction = None if self._total is not None else len(self._completed) / len(self._sizes) if self._sizes else 1.0
        self._app.get("tasks", TaskManager).progress(self._task_id, self._completed_bytes, self._total, fraction, speed)


class DownloadOperation:
    def __init__(self, app: AppManager, request: DownloadBatch) -> None:
        self._app = app
        self._request = request

    def run(self, task_id: str, cancellation: Cancellation) -> tuple[str, ...]:
        cancellation.check()
        tasks = self._app.get("tasks", TaskManager)
        snapshot = next(item for item in tasks.snapshots() if item.task_id == task_id)
        if snapshot.stages and snapshot.stage_index < 0:
            tasks.start_stage(task_id, snapshot.stages[0].key)
        manager = self._app.get("downloads", DownloadManager)
        config = self._app.get("config", CoreConfig)
        unique: dict[str, Artifact] = {}
        for artifact in self._request.artifacts:
            manager._validate(artifact)
            key = str(self._app.get("files", FileManager).path(artifact.relative_path)).casefold()
            if key in unique and unique[key] != artifact:
                raise CoreError(diagnostic('downloads.conflicting.artifacts.for.the.same.destination'))
            unique[key] = artifact
        request = DownloadBatch(tuple(unique.values()), self._request.title, self._request.item_keys)
        progress = DownloadProgress(self._app, task_id, request)
        with ThreadPoolExecutor(max_workers=config.download_workers, thread_name_prefix="launcher-download") as executor:
            futures = [executor.submit(manager.fetch, artifact, cancellation, progress) for artifact in request.artifacts]
            try:
                for future in as_completed(futures):
                    future.result()
            except Exception:
                cancellation.cancel()
                raise
        return tuple(artifact.relative_path for artifact in request.artifacts)
