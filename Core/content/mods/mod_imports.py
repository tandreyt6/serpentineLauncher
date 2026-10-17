from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from threading import RLock
from uuid import uuid4

from Core.application.application_contracts import ModQueuePrompt, ModQueueDismissed
from Core.application.application_store import ApplicationStore
from Core.application.contracts import Artifact, Cancelled, CoreError, CoreEvent
from Core.application.diagnostics import diagnostic
from Core.content.mods.mod_contracts import ModScanRequest
from Core.content.mods.mod_duplicates import duplicate_kind, file_key
from Core.content.mods.mods import ModMetadataManager
from Core.application.router import EventManager
from Core.application.storage import FileManager


@dataclass(frozen=True)
class ImportEntry:
    source: str
    destination: str
    identities: tuple[tuple[str, str], ...] = ()
    title: str = ''

    @property
    def version(self):
        return ', '.join(dict.fromkeys(version for identity, version in self.identities if version))


@dataclass
class ImportPlan:
    request_id: str
    build: object
    stage: str
    entries: tuple[ImportEntry, ...]
    folders: tuple[str, ...]
    present: list[ImportEntry]
    snapshot: dict
    targets: dict
    stages: dict
    window_key: str = ''
    cursor: int = 0
    accepted: list[ImportEntry] = field(default_factory=list)
    replacements: set[str] = field(default_factory=set)
    rollback_failed: bool = False


class ModImportManager:
    def __init__(self, app, config):
        self._app, self._config = app, config
        self._plans = {}
        self._lock = RLock()

    def handles(self, request_id):
        with self._lock:
            return request_id in self._plans

    def pending(self, build_id):
        with self._lock:
            return any(plan.build.id == build_id for plan in self._plans.values())

    def _signature(self, path):
        target = self._app.get('files', FileManager).path(path)
        if not target.exists():
            return None
        stat = target.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def _snapshot(self, build_id):
        base = f'{self._config.builds_directory}/{build_id}/mods'
        files = self._app.get('files', FileManager)
        return {base + '/' + name: self._signature(base + '/' + name) for name, folder, stamp in files.entries(base, recursive=True) if not folder and name.lower().endswith(('.jar', '.jar.disabled'))}

    def _entry(self, source, destination, cancellation):
        relative = PurePosixPath(destination).parts
        identities, title = (), PurePosixPath(destination).name
        mod_index = len(PurePosixPath(self._config.builds_directory).parts) + 1
        if len(relative) > mod_index + 1 and relative[mod_index].casefold() == 'mods' and destination.lower().endswith(('.jar', '.jar.disabled')):
            try:
                metadata = self._app.get('mods', ModMetadataManager).inspect(ModScanRequest(source, include_nested=False), cancellation)
                records = tuple(record for record in metadata.mods if not record.archive_chain)
                identities = tuple(dict.fromkeys((record.mod_id.casefold(), record.version) for record in records if record.mod_id))
                if records:
                    title = records[0].name
            except Cancelled:
                raise
            except (CoreError, OSError, ValueError):
                pass
        return ImportEntry(source, destination, identities, title)

    def add(self, build, imports, cancellation, window_key=''):
        if self.pending(build.id) or self._app.get('mod_queue', object).pending(build.id):
            raise CoreError(diagnostic('mod_queue.answer.the.pending.mod.installation.question'))
        token = uuid4().hex
        stage = f'{self._config.builds_directory}/{build.id}/{self._config.build_runtime_directory}/import-staging/{token}'
        files = self._app.get('files', FileManager)
        try:
            total = sum(path.stat().st_size for path, destination, folder in imports if not folder)
            if total > self._config.import_total_bytes:
                raise CoreError(diagnostic('mod_import.limit'))
            snapshot = self._snapshot(build.id)
            present = [self._entry(path, path, cancellation) for path in snapshot]
            entries, folders, stages, targets = [], [], {}, {}
            for index, (path, destination, folder) in enumerate(imports):
                cancellation.check()
                if folder:
                    folders.append(destination)
                    continue
                copied = stage + '/files/' + str(index) + '/' + path.name
                files.import_file(path, Artifact('', copied), cancellation, self._config.import_file_bytes)
                entries.append(self._entry(copied, destination, cancellation))
                stages[copied] = self._signature(copied)
                targets[destination] = self._signature(destination)
            plan = ImportPlan(token, build, stage, tuple(entries), tuple(folders), present, snapshot, targets, stages, window_key)
            with self._lock:
                self._plans[token] = plan
            return self._advance(plan, cancellation)
        except BaseException:
            self._discard(token, stage)
            raise

    def _matches(self, plan, entry):
        identities = {identity for identity, version in entry.identities}
        return tuple(old for old in plan.present if file_key(old.destination) == file_key(entry.destination) or identities.intersection(identity for identity, version in old.identities))

    def _prompt(self, plan):
        entry = plan.entries[plan.cursor]
        matches = self._matches(plan, entry)
        if not matches:
            return None
        kind = duplicate_kind(entry.destination, entry.version, tuple((old.destination, old.version) for old in matches))
        return ModQueuePrompt(plan.build.id, plan.request_id, kind, entry.title, window_key=plan.window_key,
                              filename=PurePosixPath(entry.destination).name, version=entry.version,
                              current_versions=tuple(old.version for old in matches), files=tuple(PurePosixPath(old.destination).name for old in matches))

    def _accept(self, plan, choice):
        entry = plan.entries[plan.cursor]
        matches = self._matches(plan, entry)
        if choice == 'replace':
            replaced = {old.destination for old in matches}
            plan.replacements.update(path for path in replaced if path in plan.snapshot)
            plan.present[:] = [old for old in plan.present if old.destination not in replaced]
            plan.accepted[:] = [old for old in plan.accepted if old.destination not in replaced]
        elif choice == 'both':
            occupied = {file_key(old.destination) for old in plan.present}
            if file_key(entry.destination) in occupied:
                path = PurePosixPath(entry.destination)
                entry = replace(entry, destination=str(path.with_name(path.stem + '.copy-' + uuid4().hex[:8] + path.suffix)))
                plan.targets[entry.destination] = None
        plan.accepted[:] = [old for old in plan.accepted if old.destination != entry.destination]
        plan.accepted.append(entry)
        plan.present.append(entry)
        plan.cursor += 1

    def _advance(self, plan, cancellation):
        while plan.cursor < len(plan.entries):
            cancellation.check()
            prompt = self._prompt(plan)
            if prompt is not None:
                self._app.get('events', EventManager).publish(CoreEvent('mod_queue_prompt', prompt))
                return prompt
            self._accept(plan, '')
        self._commit(plan, cancellation)
        self._discard(plan.request_id, plan.stage)
        self._app.get('events', EventManager).publish(CoreEvent('mod_queue_dismissed', ModQueueDismissed(plan.build.id, plan.request_id)))
        return None

    def answer(self, build_id, token, choice, cancellation):
        with self._lock:
            plan = self._plans.get(token)
        if plan is None or plan.build.id != build_id:
            raise CoreError(diagnostic('mod_queue.mod.installation.question.is.no.longer'))
        try:
            if choice == 'cancel':
                self._discard(token, plan.stage)
                self._app.get('events', EventManager).publish(CoreEvent('mod_queue_dismissed', ModQueueDismissed(build_id, token)))
                return None
            prompt = self._prompt(plan)
            if choice not in (('replace', 'both') if prompt and prompt.kind == 'duplicate' else ('replace',)):
                raise CoreError(diagnostic('mod_queue.invalid.mod.installation.answer'))
            store = self._app.get('application_store', ApplicationStore)
            if store.builds.get(build_id) != plan.build:
                raise CoreError(diagnostic('mod_import.changed'))
            self._accept(plan, choice)
            return self._advance(plan, cancellation)
        except BaseException:
            self._discard(token, plan.stage)
            self._app.get('events', EventManager).publish(CoreEvent('mod_queue_dismissed', ModQueueDismissed(build_id, token)))
            raise

    def _commit(self, plan, cancellation):
        if self._snapshot(plan.build.id) != plan.snapshot or any(self._signature(path) != signature for path, signature in (*plan.targets.items(), *plan.stages.items())):
            raise CoreError(diagnostic('mod_import.changed'))
        files = self._app.get('files', FileManager)
        backups, promoted = [], []
        try:
            for path in dict.fromkeys((*sorted(plan.replacements), *(entry.destination for entry in plan.accepted))):
                cancellation.check()
                if files.exists(path):
                    backup = plan.stage + '/backups/' + str(len(backups))
                    files.rename_file(path, backup)
                    backups.append((path, backup))
            for directory in plan.folders:
                files.ensure_directory(directory)
            for entry in plan.accepted:
                cancellation.check()
                files.rename_file(entry.source, entry.destination)
                promoted.append(entry.destination)
        except BaseException:
            failures = []
            for path in reversed(promoted):
                try:
                    files.remove_file(path)
                except (OSError, CoreError) as error:
                    failures.append(error)
            for path, backup in reversed(backups):
                try:
                    files.rename_file(backup, path)
                except (OSError, CoreError) as error:
                    failures.append(error)
            if failures:
                plan.rollback_failed = True
                raise CoreError(diagnostic('mod_import.rollback', plan.stage)) from failures[0]
            raise

    def _discard(self, token, stage):
        with self._lock:
            plan = self._plans.pop(token, None)
        if plan and plan.rollback_failed:
            return
        try:
            self._app.get('files', FileManager).remove_directory(stage)
        except OSError as error:
            self._app.log(str(error), 'WARNING')

    def close(self):
        with self._lock:
            plans = tuple(self._plans.values())
        for plan in plans:
            self._discard(plan.request_id, plan.stage)
