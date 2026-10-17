from Core.application.diagnostics import diagnostic
from Core.configuration.settings import MODRINTH_PROJECT_URL
from dataclasses import replace
from threading import RLock
from uuid import uuid4

from Core.application.application_contracts import ModAddPlan, ModConflict, ModQueuePrompt, ModQueueRecord, ModQueueDismissed
from Core.application.application_store import ApplicationStore
from Core.application.contracts import CoreError, CoreEvent
from Core.content.mods.mod_inventory import ModInventoryManager
from Core.content.providers.modrinth import ModrinthManager
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager
from Core.application.tasks import Cancellation
from Core.content.content_types import content_type
from Core.content.mods.mod_duplicates import duplicate_kind, file_key


class ModQueueManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app, self._config = app, config
        self._plans = {}
        self._lock = RLock()

    def add(self, build, project, version, title, cancellation, window_key='', content_kind='mod'):
        content_type(content_kind)
        if content_kind == 'mod' and build.loader == 'Vanilla':
            raise CoreError(diagnostic('mod_queue.vanilla.builds.do.not.support.mods'))
        if self._app.get('mod_imports', object).pending(build.id):
            raise CoreError(diagnostic('mod_queue.answer.the.pending.mod.installation.question'))
        with self._lock:
            if any(plan.build.id == build.id for plan in self._plans.values()):
                raise CoreError(diagnostic('mod_queue.answer.the.pending.mod.installation.question'))
            if len(self._plans) >= 32:
                raise CoreError(diagnostic('mod_queue.too.many.pending.mod.installation.questions'))
        store = self._app.get('application_store', ApplicationStore)
        with store.lock:
            queue = tuple(item for item in store.queue if item.owner_id == build.id)
        items = self._app.get('modrinth', ModrinthManager).plan(build, project, version, title, cancellation, content_kind)
        installed = self._app.get('mod_inventory', ModInventoryManager).scan(build, items, cancellation)
        plan = ModAddPlan(uuid4().hex, build, items, queue, installed, window_key=window_key)
        return self._advance(plan, cancellation)

    def answer(self, build_id, request_id, choice, cancellation):
        imports = self._app.get('mod_imports', object)
        if imports.handles(request_id):
            return imports.answer(build_id, request_id, choice, cancellation)
        with self._lock:
            plan = self._plans.get(request_id)
        if plan is None or plan.build.id != build_id:
            raise CoreError(diagnostic('mod_queue.mod.installation.question.is.no.longer'))
        if choice == 'cancel':
            with self._lock:
                self._plans.pop(request_id, None)
            self._app.get('events', EventManager).publish(CoreEvent('mod_queue_dismissed', ModQueueDismissed(build_id, request_id)))
            return None
        prompt = self._prompt(plan)
        choices = ('replace', 'both') if prompt and prompt.kind == 'duplicate' else ('replace',) if prompt and prompt.kind in ('file', 'same') else ('install', 'leave')
        if prompt is None or choice not in choices:
            raise CoreError(diagnostic('mod_queue.invalid.mod.installation.answer'))
        plan = replace(plan, duplicate=choice) if prompt.kind != 'dependencies' else replace(plan, dependencies=choice)
        try:
            self._validate(plan, cancellation)
            return self._advance(plan, cancellation)
        except BaseException:
            with self._lock:
                self._plans.pop(request_id, None)
            self._app.get('events', EventManager).publish(CoreEvent('mod_queue_dismissed', ModQueueDismissed(build_id, request_id)))
            raise

    def _existing(self, plan, item):
        destination = file_key(item.artifact.relative_path)
        return tuple(entry for entry in plan.installed if entry.project_id == item.project_id or file_key(entry.path) == destination) + tuple(entry for entry in plan.queue if entry.id == item.project_id or entry.artifact and file_key(entry.artifact.relative_path) == destination)

    def pending(self, build_id):
        with self._lock:
            return any(plan.build.id == build_id for plan in self._plans.values())

    def _fits(self, entry, item):
        if hasattr(entry, 'path') and entry.path.lower().endswith('.disabled'):
            return False
        if item.exact or entry.version_id == item.version_id:
            return entry.version_id == item.version_id
        return bool(set(entry.minecraft).intersection(item.minecraft) and set(entry.loaders).intersection(item.loaders))

    def _prompt(self, plan):
        root = plan.items[0]
        existing = self._existing(plan, root)
        if not plan.duplicate and existing:
            paths = tuple(entry.path if hasattr(entry, 'path') else entry.artifact.relative_path for entry in existing if hasattr(entry, 'path') or entry.artifact)
            versions = tuple(entry.number if hasattr(entry, 'number') else entry.version_number for entry in existing)
            kind = duplicate_kind(root.artifact.relative_path, root.number, tuple(zip(paths, versions)))
            if kind == 'duplicate' and any(entry.version_id == root.version_id for entry in existing):
                kind = 'same'
            return ModQueuePrompt(plan.build.id, plan.request_id, kind, root.title, window_key=plan.window_key, filename=root.artifact.relative_path.rsplit('/', 1)[-1], version=root.number, current_versions=versions, files=tuple(path.rsplit('/', 1)[-1] for path in paths))
        conflicts = []
        for item in plan.items[1:]:
            existing = self._existing(plan, item)
            if existing and not any(self._fits(entry, item) for entry in existing):
                current = tuple(entry.number if hasattr(entry, 'number') else entry.version_number or entry.version_id or '?' for entry in existing)
                disabled = any(hasattr(entry, 'path') and entry.path.lower().endswith('.disabled') for entry in existing)
                conflicts.append(ModConflict(item.title, item.required_by, item.number, current, disabled))
        if conflicts and not plan.dependencies:
            return ModQueuePrompt(plan.build.id, plan.request_id, 'dependencies', root.title, tuple(conflicts), plan.window_key)
        return None

    def _advance(self, plan, cancellation):
        prompt = self._prompt(plan)
        if prompt is not None:
            with self._lock:
                self._plans[plan.request_id] = plan
            self._app.get('events', EventManager).publish(CoreEvent('mod_queue_prompt', prompt))
            return prompt
        self._commit(plan)
        with self._lock:
            self._plans.pop(plan.request_id, None)
        self._app.get('events', EventManager).publish(CoreEvent('mod_queue_dismissed', ModQueueDismissed(plan.build.id, plan.request_id)))
        return None

    def _validate(self, plan, cancellation):
        store = self._app.get('application_store', ApplicationStore)
        with store.lock:
            current = tuple(item for item in store.queue if item.owner_id == plan.build.id)
            if store.builds.get(plan.build.id) != plan.build or current != plan.queue:
                raise CoreError(diagnostic('mod_queue.build.or.mod.queue.changed.add'))
        files = self._app.get('files', FileManager)
        kinds = tuple(content_type(key) for key in dict.fromkeys(item.content_kind for item in plan.items))
        paths = {f'{self._config.builds_directory}/{plan.build.id}/{kind.directory}/{name}' for kind in kinds for name, folder, stamp in files.entries(f'{self._config.builds_directory}/{plan.build.id}/{kind.directory}', recursive=True) if not folder and name.lower().endswith((kind.extension, kind.extension + '.disabled'))}
        if paths != {entry.path for entry in plan.installed}:
            raise CoreError(diagnostic('mod_queue.installed.mods.changed.add.the.mod'))
        for entry in plan.installed:
            if files.mod_digests(entry.path, cancellation, self._config.import_file_bytes)[0] != entry.sha512:
                raise CoreError('Installed mod changed: ' + entry.path)

    def _commit(self, plan):
        store = self._app.get('application_store', ApplicationStore)
        queue = list(plan.queue)
        occupied = {item.path.casefold() for item in plan.installed} | {item.artifact.relative_path.casefold() for item in queue if item.artifact}
        for index, item in enumerate(plan.items):
            existing = self._existing(plan, item)
            if any(entry.state != 'queued' for entry in existing if isinstance(entry, ModQueueRecord)):
                raise CoreError(diagnostic('mod_queue.cannot.change.a.mod.version.while'))
            if index and existing:
                if any(self._fits(entry, item) for entry in existing) or plan.dependencies == 'leave':
                    continue
            replacing = bool(existing) and (plan.duplicate == 'replace' if index == 0 else plan.dependencies == 'install')
            replacements = ()
            if replacing:
                replacements = tuple((entry.path, entry.sha512) for entry in existing if hasattr(entry, 'path'))
                queue = [entry for entry in queue if entry not in existing]
                replacements += tuple(pair for entry in existing if isinstance(entry, ModQueueRecord) for pair in entry.replacements)
            artifact = item.artifact
            replaced_paths = {path.casefold() for path, digest in replacements}
            if artifact.relative_path.casefold() in occupied and artifact.relative_path.casefold() not in replaced_paths:
                extension = content_type(item.content_kind).extension
                artifact = replace(artifact, relative_path=artifact.relative_path[:-len(extension)] + '.copy-' + uuid4().hex[:8] + extension)
            occupied.add(artifact.relative_path.casefold())
            queue.append(ModQueueRecord(item.project_id, item.title, MODRINTH_PROJECT_URL + '/' + item.content_kind + '/' + item.project_id, plan.build.id, version_id=item.version_id, version_number=item.number, queue_id=uuid4().hex, artifact=artifact, required_by=item.required_by, replacements=tuple(dict.fromkeys(replacements)), minecraft=item.minecraft, loaders=item.loaders, content_kind=item.content_kind, required_project_ids=item.required_project_ids))
        with store.lock:
            if store.builds.get(plan.build.id) != plan.build or tuple(item for item in store.queue if item.owner_id == plan.build.id) != plan.queue:
                raise CoreError(diagnostic('mod_queue.mod.queue.changed.add.the.mod'))
            store.persist(queue=[item for item in store.queue if item.owner_id != plan.build.id] + queue)
            store.publish()

    def validate_replacements(self, queue, cancellation):
        files = self._app.get('files', FileManager)
        for path, expected in dict(pair for item in queue for pair in item.replacements).items():
            if files.exists(path) and files.mod_digests(path, cancellation, self._config.import_file_bytes)[0] != expected:
                raise CoreError('Mod selected for replacement has changed: ' + path)

    def synchronization_queue(self, build_id, selected_kind=''):
        if selected_kind:
            content_type(selected_kind)
        store = self._app.get('application_store', ApplicationStore)
        with store.lock:
            available = tuple(item for item in store.queue if item.owner_id == build_id)
        selected = tuple(item for item in available if not selected_kind or item.content_kind == selected_kind)
        while True:
            projects = {item.id for item in selected}
            expanded = tuple(item for item in available if item in selected or projects.intersection(item.required_project_ids))
            if expanded == selected:
                return selected
            selected = expanded

    def staged_artifact(self, item):
        base = f'{self._config.builds_directory}/{item.owner_id}/{self._config.build_runtime_directory}/mod-staging/{item.queue_id or item.id}'
        return replace(item.artifact, relative_path=base + '/' + item.artifact.relative_path.rsplit('/', 1)[-1])

    def finalize(self, queue, cancellation):
        self.validate_replacements(queue, cancellation)
        files = self._app.get('files', FileManager)
        planned = tuple(item for item in queue if item.artifact)
        replaced_paths = {path.casefold() for item in queue for path, digest in item.replacements}
        for item in planned:
            if not files.cached(self.staged_artifact(item), cancellation):
                raise CoreError('Staged mod failed verification: ' + item.title)
            if files.exists(item.artifact.relative_path) and item.artifact.relative_path.casefold() not in replaced_paths and not files.cached(item.artifact, cancellation):
                raise CoreError('Mod destination has changed: ' + item.title)
        backups, promoted = [], []
        try:
            base = f'{self._config.builds_directory}/{queue[0].owner_id}/{self._config.build_runtime_directory}/mod-staging/backups/'
            for path in dict.fromkeys(path for item in queue for path, digest in item.replacements):
                cancellation.check()
                if files.exists(path):
                    backup = base + uuid4().hex + '.jar'
                    files.rename_file(path, backup)
                    backups.append((path, backup))
            for item in planned:
                cancellation.check()
                if not files.cached(item.artifact, cancellation):
                    files.copy_file(self.staged_artifact(item).relative_path, item.artifact, cancellation)
                    promoted.append(item.artifact)
            self._app.get('mod_inventory', ModInventoryManager).record_installed(queue[0].owner_id, queue, cancellation)
        except BaseException:
            for artifact in reversed(promoted):
                if files.cached(artifact, Cancellation()):
                    files.remove_file(artifact.relative_path)
            for path, backup in reversed(backups):
                files.rename_file(backup, path)
            raise
        for path, backup in backups:
            files.remove_file(backup)
        for item in planned:
            files.remove_file(self.staged_artifact(item).relative_path)

    def close(self):
        with self._lock:
            self._plans.clear()
