from Core.application.diagnostics import diagnostic
import re
from threading import RLock

from datetime import datetime
from pathlib import PurePosixPath

from Core.application.application_contracts import EditorSnapshot, FileEntry, ModEntry
from Core.application.contracts import Cancelled, CoreError, CoreEvent
from Core.content.mods.mod_contracts import ModScanRequest
from Core.content.mods.mods import ModMetadataManager
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager, checked_relative, safe_identifier
from Core.application.tasks import Cancellation
from Core.application.log_format import format_log


class EditorFilesManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._mod_cache = {}
        self._snapshots = {}
        self._log_cache = {}
        self._cache_lock = RLock()

    def _publish(self, result):
        with self._cache_lock:
            if self._snapshots.get(result.build_id) == result:
                return
            self._snapshots[result.build_id] = result
        self._app.get('events', EventManager).publish(CoreEvent('editor', result))

    def path(self, build: str, relative: str) -> str:
        safe_identifier(build)
        checked_relative(relative)
        files = self._app.get("files", FileManager)
        root = files.path(f"{self._config.builds_directory}/{build}")
        path = files.path(f"{self._config.builds_directory}/{build}/{relative}")
        if not path.is_relative_to(root):
            raise ValueError(diagnostic('editor_files.file.escapes.its.build'))
        return f"{self._config.builds_directory}/{build}/{relative}"

    def writable_path(self, build: str, relative: str) -> str:
        path = self.path(build, relative)
        parts = PurePosixPath(relative).parts
        if parts[0].casefold() == self._config.build_runtime_directory.casefold() or relative.casefold() == self._config.build_metadata_filename.casefold() or relative.casefold() == (self._config.build_metadata_filename + ".removed").casefold():
            raise CoreError(diagnostic('editor_files.launcher.managed.files.cannot.be.modified'))
        return path

    def is_config(self, relative: str) -> bool:
        path = PurePosixPath(relative)
        if path.parts[0].casefold() in ("mods", "resourcepacks", "shaderpacks", "saves", self._config.build_logs_directory.casefold(), self._config.build_runtime_directory.casefold()):
            return False
        return path.suffix.casefold() in self._config.config_file_extensions and path.name.casefold() != self._config.build_metadata_filename.casefold()

    def scan(self, build: str, cancellation: Cancellation) -> EditorSnapshot:
        cancellation.check()
        safe_identifier(build)
        files = self._app.get("files", FileManager)
        entries = {}
        logs = []
        mods = []
        base = f"{self._config.builds_directory}/{build}"
        with self._cache_lock:
            previous = self._snapshots.get(build)
        if previous:
            entries.update((item.path, item) for item in previous.files if PurePosixPath(item.path).parts[0].casefold() not in ('mods', 'resourcepacks', 'shaderpacks'))
        inventory = {}
        roots = files.entries(base)
        for kind in ('mods', 'resourcepacks', 'shaderpacks'):
            directory = next((name for name, folder, _ in roots if folder and name.casefold() == kind), None)
            if directory is None:
                continue
            try:
                for name, folder, stamp in files.iter_entries(base + '/' + directory, recursive=kind == 'mods'):
                    cancellation.check()
                    relative = directory + '/' + name
                    inventory[relative] = folder, stamp
                    entries[relative] = FileEntry(relative, PurePosixPath(relative).name, folder)
            except Cancelled:
                raise
            except (OSError, CoreError) as error:
                self._app.log(diagnostic('editor_files.scan.warning', base + '/' + directory, error), 'WARNING')
        signatures = {}
        for relative, (folder, _) in inventory.items():
            name = PurePosixPath(relative).name
            if folder or PurePosixPath(relative).parts[0].casefold() != 'mods' or not name.lower().endswith(('.jar', '.jar.disabled')):
                continue
            source = self.path(build, relative)
            try:
                stat = files.path(source).stat()
                signature = stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
            except OSError:
                signature = None
            signatures[source] = signature
            with self._cache_lock:
                cached = self._mod_cache.get(source)
            mods.append(cached[1] if cached and cached[0] == signature else ModEntry(relative, name.removesuffix('.disabled'), '', '', '', '', name.lower().endswith('.jar')))
        self._publish(EditorSnapshot(build, tuple(sorted(entries.values(), key=lambda item: item.path)), previous.logs if previous else (), tuple(mods)))
        manager = self._app.get('mods', ModMetadataManager)
        for index, entry in enumerate(mods):
            cancellation.check()
            source = self.path(build, entry.path)
            signature = signatures[source]
            with self._cache_lock:
                cached = self._mod_cache.get(source)
            if cached and cached[0] == signature:
                continue
            try:
                metadata = manager.inspect(ModScanRequest(source, include_nested=False), cancellation)
                record = metadata.mods[0] if metadata.mods else None
                icon = manager.icon_for(metadata, record.record_key) if record else None
                cached_icon = manager.cache_icon(icon, cancellation).relative_path if icon else ''
                if record:
                    mods[index] = ModEntry(entry.path, record.name, record.version, record.description, ', '.join(person.name for person in record.authors), cached_icon, entry.enabled)
            except Cancelled:
                raise
            except Exception as error:
                self._app.log(diagnostic('editor_files.scan.warning', source, error), 'WARNING')
            if signature is not None:
                with self._cache_lock:
                    self._mod_cache[source] = signature, mods[index]
        with self._cache_lock:
            for source in tuple(self._mod_cache):
                if source.startswith(base + '/') and source not in signatures:
                    self._mod_cache.pop(source)
        self._publish(EditorSnapshot(build, tuple(sorted(entries.values(), key=lambda item: item.path)), previous.logs if previous else (), tuple(mods)))
        entries = {path: item for path, item in entries.items() if PurePosixPath(path).parts[0].casefold() in ('mods', 'resourcepacks', 'shaderpacks')}
        try:
            for relative, folder, stamp in files.iter_entries(base, recursive=True, exclude=(self._config.build_runtime_directory,)):
                cancellation.check()
                name = PurePosixPath(relative).name
                if name.casefold() in (self._config.build_metadata_filename.casefold(), (self._config.build_metadata_filename + '.removed').casefold()):
                    continue
                entries[relative] = FileEntry(relative, name, folder, config=not folder and self.is_config(relative))
                if not folder and PurePosixPath(relative).parts[0].casefold() == self._config.build_logs_directory.casefold() and name.lower().endswith(('.log', '.txt')):
                    try:
                        source = self.path(build, relative)
                        stat = files.path(source).stat()
                        signature = stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
                        with self._cache_lock:
                            cached = self._log_cache.get(source)
                        if cached and cached[0] == signature:
                            logs.append(cached[1])
                            continue
                        text = files.read_tail(source, self._config.mod_metadata_bytes).decode('utf-8', errors='replace')
                        date = re.search(r'\d{4}-\d{2}-\d{2}', name)
                        date_text = date.group() if date else datetime.fromtimestamp(float(stamp)).strftime('%Y-%m-%d')
                        record = FileEntry(relative, name, False, date_text, text, formatted_text=format_log(text, cancellation.check))
                        with self._cache_lock:
                            self._log_cache[source] = signature, record
                        logs.append(record)
                    except Cancelled:
                        raise
                    except (OSError, CoreError) as error:
                        self._app.log(diagnostic('editor_files.scan.warning', base + '/' + relative, error), 'WARNING')
        except Cancelled:
            raise
        except (OSError, CoreError) as error:
            self._app.log(diagnostic('editor_files.scan.warning', base, error), 'WARNING')
        with self._cache_lock:
            retained_logs = {self.path(build, log.path) for log in logs}
            for source in tuple(self._log_cache):
                if source.startswith(base + '/') and source not in retained_logs:
                    self._log_cache.pop(source)
        result = EditorSnapshot(build, tuple(sorted(entries.values(), key=lambda item: item.path)), tuple(logs), tuple(mods))
        self._publish(result)
        return result
