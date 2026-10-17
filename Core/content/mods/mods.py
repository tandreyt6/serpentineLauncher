from Core.application.diagnostics import diagnostic
import hashlib
import zipfile

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

from Core.application.contracts import Artifact, CoreError, CoreEvent, Digest
from Core.content.mods.mod_archive import ModArchiveReader
from Core.content.mods.mod_contracts import CachedModIcon, ModIconAsset, ModJarMetadata, ModScanRequest
from Core.content.mods.mod_icons import sanitized_png
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager
from Core.application.tasks import Cancellation, TaskManager


def result_cache_bytes(result: ModJarMetadata) -> int:
    return sum(len(icon.png_bytes) for icon in result.icons) + len(repr((result.relative_path, result.descriptors, result.mods, result.diagnostics)).encode("utf-8"))


class ModMetadataManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._lock = RLock()
        self._cache: OrderedDict[tuple[str, str, bool], tuple[ModJarMetadata, int]] = OrderedDict()
        self._cache_bytes = 0
        self._closed = False

    def inspect(self, request: ModScanRequest, cancellation: Cancellation | None = None) -> ModJarMetadata:
        token = cancellation or Cancellation()
        token.check()
        with self._lock:
            if self._closed:
                raise CoreError(diagnostic('mods.mod.metadata.manager.is.closed'))
        if type(request.include_nested) is not bool or not isinstance(request.relative_path, str) or not request.relative_path.lower().endswith((".jar", ".jar.disabled")):
            raise CoreError(diagnostic('mods.a.relative.jar.or.jar.disabled'))
        files = self._app.get("files", FileManager)
        try:
            data = files.read(request.relative_path, self._config.mod_jar_bytes)
            token.check()
            digest = hashlib.sha256(data).hexdigest()
            key = (request.relative_path, digest, request.include_nested)
            with self._lock:
                cached = self._cache.get(key)
                if cached is not None:
                    self._cache.move_to_end(key)
                    result = cached[0]
                else:
                    result = None
            if result is None:
                result = ModArchiveReader(self._config, token).scan(data, request.relative_path, request.include_nested)
                self._remember(key, result)
        except (OSError, zipfile.BadZipFile, ValueError) as error:
            raise CoreError(diagnostic('mods.cannot.inspect.mod.archive', error)) from error
        token.check()
        self._app.get("events", EventManager).publish(CoreEvent("mod_metadata", result))
        return result

    def _remember(self, key: tuple[str, str, bool], result: ModJarMetadata) -> None:
        cost = result_cache_bytes(result)
        if cost > self._config.mod_cache_bytes:
            return
        with self._lock:
            if self._closed:
                return
            old = self._cache.pop(key, None)
            if old:
                self._cache_bytes -= old[1]
            self._cache[key] = (result, cost)
            self._cache_bytes += cost
            while len(self._cache) > self._config.mod_cache_entries or self._cache_bytes > self._config.mod_cache_bytes:
                _, (_, removed_cost) = self._cache.popitem(last=False)
                self._cache_bytes -= removed_cost

    def submit(self, request: ModScanRequest) -> str:
        operation = ModScanOperation(self._app, request)
        return self._app.get("tasks", TaskManager).submit(f"Inspect mod {request.relative_path}", operation.run)

    def icon_for(self, result: ModJarMetadata, record_key: str, target_pixels: int = 64) -> ModIconAsset | None:
        if type(target_pixels) is not int or target_pixels < 1:
            raise CoreError(diagnostic('mods.requested.icon.size.must.be.positive'))
        record = next((record for record in result.mods if record.record_key == record_key), None)
        if record is None:
            raise CoreError(diagnostic('mods.unknown.mod.record'))
        paths = {reference.member_path for reference in record.icons}
        icons = [icon for icon in result.icons if icon.archive_chain == record.archive_chain and icon.member_path in paths]
        if not icons:
            return None
        sufficient = [icon for icon in icons if min(icon.width, icon.height) >= target_pixels]
        return min(sufficient, key=self._icon_area) if sufficient else max(icons, key=self._icon_area)

    @staticmethod
    def _icon_area(icon: ModIconAsset) -> int:
        return icon.width * icon.height

    def cache_icon(self, icon: ModIconAsset, cancellation: Cancellation | None = None) -> CachedModIcon:
        token = cancellation or Cancellation()
        token.check()
        width, height, png = sanitized_png(icon.png_bytes, self._config)
        digest = hashlib.sha256(png).hexdigest()
        if (width, height, digest) != (icon.width, icon.height, icon.sha256):
            raise CoreError(diagnostic('mods.icon.dto.failed.integrity.verification'))
        relative_path = f"{self._config.cores_directory}/{self._config.cache_directory}/{self._config.mod_icon_cache_directory}/{digest}.png"
        artifact = Artifact("", relative_path, len(png), (Digest("sha256", digest),))
        files = self._app.get("files", FileManager)
        with self._lock:
            if self._closed:
                raise CoreError(diagnostic('mods.mod.metadata.manager.is.closed'))
            if not files.cached(artifact, token):
                stage = files.begin(relative_path)
                try:
                    files.append(stage, png)
                    files.commit(stage, artifact, token)
                finally:
                    files.discard(stage)
        return CachedModIcon(relative_path, digest, width, height)

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
class ModScanOperation:
    app: AppManager
    request: ModScanRequest

    def run(self, task_id: str, cancellation: Cancellation) -> ModJarMetadata:
        return self.app.get("mods", ModMetadataManager).inspect(self.request, cancellation)
