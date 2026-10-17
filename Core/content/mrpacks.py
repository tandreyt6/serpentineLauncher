from Core.application.diagnostics import diagnostic
import hashlib
import zipfile

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

from Core.application.contracts import CoreError, CoreEvent
from Core.content.mrpack_contracts import MrpackMetadata, MrpackScanRequest
from Core.content.mrpack_parser import MrpackReader
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager
from Core.application.tasks import Cancellation, TaskManager


class MrpackMetadataManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._lock = RLock()
        self._cache: OrderedDict[tuple[str, str], tuple[MrpackMetadata, int]] = OrderedDict()
        self._cache_bytes = 0
        self._closed = False

    def inspect(self, request: MrpackScanRequest, cancellation: Cancellation | None = None) -> MrpackMetadata:
        token = cancellation or Cancellation()
        token.check()
        with self._lock:
            if self._closed:
                raise CoreError(diagnostic('mrpacks.mrpack.metadata.manager.is.closed'))
        if not isinstance(request.relative_path, str) or not request.relative_path.lower().endswith(".mrpack"):
            raise CoreError(diagnostic('mrpacks.a.relative.mrpack.file.path.is'))
        try:
            data = self._app.get("files", FileManager).read(request.relative_path, self._config.mrpack_archive_bytes)
            token.check()
            key = (request.relative_path, hashlib.sha256(data).hexdigest())
            with self._lock:
                cached = self._cache.get(key)
                if cached is not None:
                    self._cache.move_to_end(key)
            result = cached[0] if cached else MrpackReader(self._config, token).scan(data, request.relative_path)
            if cached is None:
                self._remember(key, result)
        except (OSError, zipfile.BadZipFile, ValueError) as error:
            raise CoreError(diagnostic('mrpacks.cannot.inspect.mrpack', error)) from error
        token.check()
        self._app.get("events", EventManager).publish(CoreEvent("mrpack_metadata", result))
        return result

    def _remember(self, key: tuple[str, str], result: MrpackMetadata) -> None:
        cost = len(repr(result).encode("utf-8"))
        if cost > self._config.mrpack_cache_bytes:
            return
        with self._lock:
            if self._closed:
                return
            previous = self._cache.pop(key, None)
            if previous:
                self._cache_bytes -= previous[1]
            self._cache[key] = (result, cost)
            self._cache_bytes += cost
            while len(self._cache) > self._config.mrpack_cache_entries or self._cache_bytes > self._config.mrpack_cache_bytes:
                _, (_, removed) = self._cache.popitem(last=False)
                self._cache_bytes -= removed

    def submit(self, request: MrpackScanRequest) -> str:
        operation = MrpackScanOperation(self._app, request)
        return self._app.get("tasks", TaskManager).submit(f"Inspect pack {request.relative_path}", operation.run)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._cache_bytes = 0

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._cache.clear()
            self._cache_bytes = 0


@dataclass(frozen=True)
class MrpackScanOperation:
    app: AppManager
    request: MrpackScanRequest

    def run(self, task_id: str, cancellation: Cancellation) -> MrpackMetadata:
        return self.app.get("mrpacks", MrpackMetadataManager).inspect(self.request, cancellation)
