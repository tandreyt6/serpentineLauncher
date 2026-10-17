from dataclasses import asdict, replace
from collections import OrderedDict
from time import monotonic
import re

from PySide6.QtCore import QFileSystemWatcher, Property, QTimer, QUrl, Slot
from PySide6.QtGui import QDesktopServices

from Core.configuration.settings import APPLICATION_SETTINGS, BACKEND_EVENT_INTERVAL_MS, BACKEND_BUSY_EVENT_INTERVAL_MS, BACKEND_EVENT_DRAIN_BUDGET_MS, CORE_BROWSER_FILTER_CACHE_ENTRIES, CORE_BROWSER_FILTER_CACHE_ROWS, CORE_DOWNLOAD_SPEED_WINDOW_SECONDS, EDITOR_FILE_CHANGE_DELAY_MS
from Core.application.application import ApplicationManager
from Core.application.application_store import ApplicationStore
from Core.application.first_run import FirstRunSetup
from Core.content.versions import version_key
from Core.application.application_contracts import ApplicationCommand, ApplicationSnapshot, BackendResult, CatalogueState, CoreBrowseResult, EditorSnapshot, ModSearchResult, ModProjectResult, ModIconResult, ModFiltersResult, VersionCatalogue, ModQueuePrompt, ModQueueDismissed
from Core.application.contracts import ClientSnapshot, CoreEvent, InstalledCore, TaskSnapshot, DownloadItemProgress
from Core.game.launch import LaunchManager
from Core.application.router import EventManager
from Core.application.runtime import CoreRuntime
from Core.application.settings import CoreConfig
from Core.application.storage import safe_identifier
from Core.application.tasks import TaskManager
from Core.presentation.contracts import AccountPreview, BuildDecorationPreview, BuildPreview, CorePreview, CreateBuildPreview, DownloadPreview, EditorCommand, PreviewCommand
from Core.presentation.session import PreviewSession
from universal_gui.contracts import Event, LocaleCatalog, Request, SettingChange, TextQuery


class LiveSession(PreviewSession):
    def __init__(self, router, core: CoreRuntime, *, bootstrapped=False) -> None:
        super().__init__(router, demo=False)
        self._core = core
        self._settings = dict(APPLICATION_SETTINGS)
        self._snapshot = None
        self._clients: dict[str, ClientSnapshot] = {item.build_id: item for item in core.app.get("launch", LaunchManager).snapshots()}
        self._tasks: dict[str, TaskSnapshot] = {item.task_id: item for item in core.app.get("tasks", TaskManager).snapshots()}
        self._links: dict[str, tuple[str, str]] = {item.text: (item.action.split(".")[1], item.key) for item in core.app.get("application", ApplicationManager).task_links()}
        self._editor: dict[str, EditorSnapshot] = {}
        self._editor_paths = {}
        self._active_editor_builds = set()
        self._editor_pending = set()
        self._editor_scans = {}
        self._speed_updates = {}
        self._editor_watcher = QFileSystemWatcher(self)
        self._editor_watcher.directoryChanged.connect(self._editor_directory_changed)
        self._editor_refresh = QTimer(self)
        self._editor_refresh.setSingleShot(True)
        self._editor_refresh.setInterval(EDITOR_FILE_CHANGE_DELAY_MS)
        self._editor_refresh.timeout.connect(self._refresh_editor_files)
        self._memory = 512
        self._versions: tuple[str, ...] = ()
        self._minecraft_versions: tuple[str, ...] = ()
        self._installed_core_versions: tuple[str, ...] = ()
        self._restored = False
        self._submitted_tasks: set[str] = set()
        self._dismissed_tasks: set[str] = set()
        self._catalog_pending: set[tuple[str, str]] = set()
        self._catalog_tasks: dict[str, tuple[str, str]] = {}
        self._catalog_again: set[tuple[str, str]] = set()
        self._catalogue_state = CatalogueState(0, False, ())
        self._editor_revision = 0
        self._registered_builds = None
        self._batching = False
        self._needs_projection = False
        self._needs_core_browser = False
        self._needs_general_change = False
        self._projected_core_source = None
        self._projected_core_active = {}
        self._projected_core_indices = {}
        self._browse_generation = 0
        self._browse_filter = None
        self._browse_choices = ()
        self._browse_more = False
        self._browse_busy = False
        self._browse_task = ""
        self._browse_versions = ()
        self._browse_pages: OrderedDict[tuple[str, str, str], CoreBrowseResult] = OrderedDict()
        self._timer = QTimer(self)
        self._timer.setInterval(BACKEND_EVENT_INTERVAL_MS)
        self._timer.timeout.connect(self._drain)
        events = self._core.app.get("events", EventManager)
        for topic in ("application", "backend", "task", "client", "core.installed", "core.browse", "core.versions", "core.catalogue", "editor", "mod_search", 'mod_project', 'mod_icon', 'mod_filters', 'mod_queue_prompt', 'mod_queue_dismissed', 'download.item', 'first_run'):
            events.subscribe(topic, self._event)
        self._timer.start()
        if not bootstrapped:
            self._submit(ApplicationCommand("bootstrap", fields=(("prepare_resources", "true"),)))

    live = Property(bool, lambda self: True, constant=True)

    @Slot()
    def prepareFirstRun(self):
        if self._closing or self._first_run_requested or self._snapshot is None:
            return
        self._first_run_requested = True
        if not self._settings['firstRunComplete']:
            self._submit(ApplicationCommand('prepare_first_run'))

    @Slot()
    def acknowledgeFirstRun(self):
        if self._first_run_setup is None or self._closing:
            return
        super().acknowledgeFirstRun()
        self._submit(ApplicationCommand('setting', 'firstRunComplete', 'true'))
    memoryLimit = Property(int, lambda self: self._memory, notify=PreviewSession.changed)
    minecraftVersions = Property("QVariantList", lambda self: list(self._minecraft_versions), notify=PreviewSession.minecraftVersionsChanged)
    installedCoreVersions = Property("QVariantList", lambda self: list(self._installed_core_versions), notify=PreviewSession.installedCoreVersionsChanged)
    editorRevision = Property(int, lambda self: self._editor_revision, notify=PreviewSession.editorChanged)
    coreBrowserMore = Property(bool, lambda self: self._browse_more, notify=PreviewSession.coreBrowserChanged)
    coreBrowserBusy = Property(bool, lambda self: self._browse_busy, notify=PreviewSession.coreBrowserChanged)
    coreBrowserVersions = Property("QVariantList", lambda self: list(self._browse_versions or self._versions), notify=PreviewSession.coreBrowserVersionsChanged)

    catalogueUpdating = Property(bool, lambda self: self._catalogue_state.updating, notify=PreviewSession.catalogueStateChanged)

    @Slot(str, str, str)
    def browseCores(self, state: str, loader: str, minecraft: str) -> None:
        filters = (state, loader, minecraft)
        if filters == self._browse_filter and (self._browse_busy or filters in self._browse_pages):
            return
        self._begin_core_browse(filters)

    def _begin_core_browse(self, filters: tuple[str, str, str]) -> None:
        if self._browse_task and self._browse_busy:
            self._core.app.get("tasks", TaskManager).cancel(self._browse_task)
        self._browse_generation += 1
        previous = self._browse_filter
        self._browse_filter = filters
        cached = self._browse_pages.get(filters)
        if cached is not None:
            self._browse_pages.move_to_end(filters)
            self._browse_choices = cached.cores
            self._browse_more = cached.more
            self._browse_busy = False
            self._browse_task = ""
            self._update_core_browser()
            self.coreBrowserChanged.emit()
            return
        if previous != filters:
            state, loader, minecraft = filters
            active = {owner for task_id, (kind, owner) in self._links.items() if kind == "core" and self._tasks.get(task_id) and self._tasks[task_id].state in ("queued", "running", "retrying", "paused", "cancelling")}
            self._browse_choices = tuple(core for core in self._snapshot.cores if (core.installed or core.id in active) and (not loader or core.loader == loader) and (not minecraft or core.minecraft == minecraft) and (state == "all" or core.installed == (state == "installed"))) if self._snapshot else ()
        self._browse_more = False
        self._update_core_browser()
        self._request_core_page(0)

    @Slot()
    def loadMoreCores(self) -> None:
        if self._browse_more and not self._browse_busy:
            self._request_core_page(len(self._browse_choices))

    def _request_core_page(self, offset: int) -> None:
        state, loader, minecraft = self._browse_filter
        self._browse_busy = True
        self.coreBrowserChanged.emit()
        self._browse_task = self._submit(ApplicationCommand("browse_cores", loader, minecraft, (("state", state), ("offset", str(offset)), ("request_id", str(self._browse_generation)))))

    def _refresh_core_browser(self) -> None:
        self._browse_pages.clear()
        if self._browse_filter is not None:
            self._begin_core_browse(self._browse_filter)

    def _update_core_browser(self) -> None:
        if self._batching:
            self._needs_core_browser = True
            return
        active = {}
        for task_id, (kind, owner) in self._links.items():
            task = self._tasks.get(task_id)
            if kind == "core" and task and task.state in ("queued", "running", "retrying", "paused", "cancelling"):
                active[owner] = (self._task_progress(task), task.state == "paused", self._task_stage(task))
        items = tuple(CorePreview(core.id, core.minecraft, core.loader, core.version, core.installed, *active.get(core.id, (-1, False, ""))) for core in self._browse_choices)
        self._core_browser_model.synchronize(items)

    @staticmethod
    def _task_progress(task: TaskSnapshot) -> float:
        fraction = task.progress if task.progress is not None else task.completed_bytes / task.total_bytes if task.total_bytes else 0.0
        return min(99.999, max(0.0, 100 * fraction))

    def _task_stage(self, task: TaskSnapshot) -> str:
        if not task.stages:
            return ""
        if task.stage_index < 0:
            return self.text("task.stage.waiting")
        key = task.stages[task.stage_index].key
        label = self.text("task.stage.processor") + " " + str(int(key.rsplit(".", 1)[1]) + 1) if key.startswith("installer.processor.") else self.text("task.stage." + key) if key in ("metadata", "libraries", "assets", "installer", "finalize", "download", "installer.dependencies", "installer.finalize") else key
        return label + " · " + str(task.stage_index + 1) + "/" + str(len(task.stages))

    def _locale_changed(self, event: Event) -> None:
        super()._locale_changed(event)
        self._project()
        self._update_core_browser()

    def _submit(self, command: ApplicationCommand) -> str:
        task = self._core.app.get("application", ApplicationManager).submit(command)
        self._submitted_tasks.add(task)
        return task

    def _watch_editor(self, key):
        safe_identifier(key)
        if key not in self._active_editor_builds:
            return
        config = self._core.app.get('config', CoreConfig)
        build = config.root / config.builds_directory / key
        paths = tuple(str(path) for path in (build, build / 'mods', build / 'resourcepacks', build / 'shaderpacks') if path.is_dir())
        self._editor_paths[key] = paths
        missing = set(paths) - set(self._editor_watcher.directories())
        if missing:
            self._editor_watcher.addPaths(list(missing))

    @Slot('QVariantList')
    def watchEditorBuilds(self, builds):
        self._active_editor_builds = set(builds)
        self._editor_pending.intersection_update(self._active_editor_builds)
        for key in set(self._editor_paths) - self._active_editor_builds:
            self._editor_paths.pop(key)
        for key in self._active_editor_builds:
            self._watch_editor(key)
        wanted = {path for paths in self._editor_paths.values() for path in paths}
        stale = set(self._editor_watcher.directories()) - wanted
        if stale:
            self._editor_watcher.removePaths(list(stale))

    def _editor_directory_changed(self, path):
        self._editor_pending.update(key for key, paths in self._editor_paths.items() if path in paths)
        if not self._editor_refresh.isActive():
            self._editor_refresh.start()

    def _scan_editor(self, key):
        self._watch_editor(key)
        if key in self._editor_scans.values():
            self._editor_pending.add(key)
            return
        task = self._submit(ApplicationCommand('editor_scan', key))
        self._editor_scans[task] = key

    def _refresh_editor_files(self):
        pending, self._editor_pending = self._editor_pending, set()
        for key in pending:
            self._scan_editor(key)

    def _error_text(self, error: str) -> str:
        keys = {
            "Offline username must contain 3-16 letters, digits or underscores": "validation.account_name",
            "Account already exists": "validation.account_duplicate",
            "No installed Java runtime meets the requested version": "error.java.required",
            "Java executable does not exist": "error.java.missing",
            "Executable did not identify itself as a Java runtime": "error.java.invalid",
            "Java runtime verification failed": "error.java.probe",
            "Installer Java is older than the Minecraft Java requirement": "error.java.installer_version",
            "Java architecture must match the selected native libraries": "error.java.architecture",
            "Minecraft installation is incomplete; finish downloading before launching": "error.minecraft.incomplete",
        }
        if error in keys:
            return self.text(keys[error])
        version = re.fullmatch(r"Minecraft requires Java ([0-9]+) or newer", error)
        if version:
            return self._router.request(Request("localization", "text", TextQuery("error.java.version", (("version", version.group(1)),))))
        return error

    @Slot()
    def _drain(self) -> None:
        self._batching = True
        try:
            events = self._core.app.get("events", EventManager)
            events.drain(maximum_ms=BACKEND_EVENT_DRAIN_BUDGET_MS)
        finally:
            self._batching = False
        now = monotonic()
        for task_id, stamp in tuple(self._speed_updates.items()):
            if now - stamp >= CORE_DOWNLOAD_SPEED_WINDOW_SECONDS:
                self._speed_updates.pop(task_id)
                if task_id in self._tasks:
                    self._tasks[task_id] = replace(self._tasks[task_id], bytes_per_second=0.0)
                    self._needs_projection = True
        if self._needs_projection:
            self._needs_projection = False
            self._project()
        if self._needs_core_browser:
            self._needs_core_browser = False
            self._update_core_browser()
        self._timer.setInterval(BACKEND_BUSY_EVENT_INTERVAL_MS if events.has_pending() else BACKEND_EVENT_INTERVAL_MS)

    def _event(self, event: CoreEvent) -> None:
        payload = event.payload
        if isinstance(payload, FirstRunSetup):
            self._first_run_setup = payload
            self.firstRunChanged.emit()
        elif isinstance(payload, ModQueuePrompt):
            self.modQueueDecision.emit({**asdict(payload), 'current_versions': list(payload.current_versions), 'files': list(payload.files), 'conflicts': [{**asdict(item), 'required_by': list(item.required_by), 'current': list(item.current)} for item in payload.conflicts]})
        elif isinstance(payload, ModQueueDismissed):
            self.modQueueDecisionDismissed.emit(payload.build_id, payload.request_id)
        elif isinstance(payload, ApplicationSnapshot):
            self._needs_general_change = True
            previous = self._snapshot
            self._snapshot = payload
            self._accounts = [AccountPreview(item.id, item.name, item.name[:2].upper()) for item in payload.accounts]
            self._account = payload.account
            self._settings = {**APPLICATION_SETTINGS, **dict(payload.settings)}
            self._memory = payload.memory_limit
            self._versions = payload.minecraft_versions
            if not self._browse_versions and (previous is None or previous.minecraft_versions != payload.minecraft_versions):
                self.coreBrowserVersionsChanged.emit()
            queue = list(payload.queue)
            if queue != self._mod_queue:
                self._mod_queue = queue


                self._sync_content_queues()
            if previous is not None:
                old_builds = {item.id: (item.minecraft, item.loader) for item in previous.builds}
                for build in payload.builds:
                    if old_builds.get(build.id) != (build.minecraft, build.loader):
                        for identity, browser in self._mod_browsers.items():
                            if (identity if isinstance(identity, str) else identity[0]) == build.id:
                                browser.invalidate()
                    if old_builds.get(build.id) != (build.minecraft, build.loader):
                        for (owner, _), project in self._mod_projects.items():
                            if owner == build.id:
                                project.invalidate()
                for key in tuple(self._mod_browsers):
                    if (key if isinstance(key, str) else key[0]) not in {item.id for item in payload.builds}:
                        self._mod_browsers.pop(key).deleteLater()
                for owner, project_id in tuple(self._mod_projects):
                    if owner not in {item.id for item in payload.builds}:
                        project = self._mod_projects[(owner, project_id)]
                        self.releaseModProject(owner, project.project_id, project.content_kind)
                for identity in tuple(self._content_queues):
                    if identity[0] not in {item.id for item in payload.builds}:
                        self._content_queues.pop(identity).deleteLater()
            if not self._restored:
                self._restored = True
                for service, key in (("themes", "theme"), ("localization", "locale")):
                    selected = self._settings.get(key)
                    if selected in self._router.request(Request(service, "available")):
                        self._router.request(Request(service, "select", selected))
            self._sync_presentation_settings()
            self._project()
            if self._browse_filter is not None and (previous is None or previous.cores != payload.cores):
                self._refresh_core_browser()
        elif isinstance(payload, TaskSnapshot):
            previous = self._tasks.get(payload.task_id)
            self._tasks[payload.task_id] = payload
            if payload.bytes_per_second > 0:
                self._speed_updates[payload.task_id] = monotonic()
            else:
                self._speed_updates.pop(payload.task_id, None)
            if payload.state in ('failed', 'cancelled', 'completed'):
                owner = self._editor_scans.pop(payload.task_id, None)
                if owner in self._editor_pending:
                    self._editor_refresh.start()
            if payload.state in ("failed", "cancelled", "completed"):
                for browser in self._mod_browsers.values():
                    browser.task_finished(payload.task_id, payload.state, self._error_text(payload.error) if payload.error else "")
                for project in self._mod_projects.values():
                    project.task_finished(payload.task_id, payload.state, self._error_text(payload.error) if payload.error else '')
            if payload.state == "failed" and (previous is None or previous.state != "failed"):
                self.notice.emit(self._error_text(payload.error))
            if payload.state in ("failed", "completed", "cancelled") and payload.task_id in self._catalog_tasks:
                pair = self._catalog_tasks.pop(payload.task_id)
                self._catalog_pending.discard(pair)
                if pair in self._catalog_again:
                    self._catalog_again.discard(pair)
                    self.requestVersions(*pair)
                self._version_catalogue_revision += 1
                self.versionCatalogueChanged.emit()
            if payload.task_id == self._browse_task and payload.state in ("failed", "cancelled"):
                self._browse_busy = False
                self.coreBrowserChanged.emit()
            if payload.task_id in self._links and self._links[payload.task_id][0] == "core":
                self._update_core_browser()
                if payload.state in ("failed", "completed", "cancelled") and (previous is None or previous.state != payload.state):
                    self._refresh_core_browser()
            if payload.state in ("failed", "cancelled") and (previous is None or previous.state != payload.state):
                link = self._links.get(payload.task_id)
                if link is not None and link[0] == "mod":
                    self._submit(ApplicationCommand("editor_scan", link[1]))
            self._project()
            if (payload.state in ("completed", "cancelled") or payload.state == 'failed' and not payload.can_retry) and payload.task_id in self._submitted_tasks:
                self._submitted_tasks.discard(payload.task_id)
                self._tasks.pop(payload.task_id, None)
                self._core.app.get("tasks", TaskManager).release(payload.task_id)
        elif isinstance(payload, ClientSnapshot):
            previous = self._clients.get(payload.build_id)
            self._clients[payload.build_id] = payload
            if payload.launch_origin != "editor" and payload.state == "running" and (previous is None or previous.state != "running"):
                self.windowAction.emit(self._settings["launchAction"])
            if payload.launch_origin != "editor" and payload.state in ("exited", "failed") and previous is not None and previous.state in ("starting", "running", "closing"):
                if self._settings["finishAction"] == "each" or self._settings["finishAction"] == "last" and not any(item.state in ("starting", "running", "closing") for item in self._clients.values()):
                    self.windowAction.emit("show")
            self._project()
        elif isinstance(payload, BackendResult):
            if payload.action == "activate":
                self.windowAction.emit("show")
            elif payload.action in ("task.core", "task.mod", "task.resources"):
                self._links[payload.text] = (payload.action.split(".")[1], payload.key)
                if payload.action == "task.core":
                    self._refresh_core_browser()
                self._project()
            elif payload.action == "created":
                self._selected = payload.key
                self.changed.emit()
            elif payload.action == "open_path":
                QDesktopServices.openUrl(QUrl.fromLocalFile(payload.path))
            elif payload.action == "file_read":
                self.fileLoaded.emit(payload.key, payload.path, payload.text)
            elif payload.action == "file_saved":
                self.fileSaved.emit(payload.key, payload.path, payload.text)
            elif payload.action == "saved":
                self.buildSaved.emit(payload.key)
        elif isinstance(payload, EditorSnapshot):
            self._editor[payload.build_id] = payload
            self._watch_editor(payload.build_id)
            self._editor_revision += 1
            self.editorChanged.emit()
        elif isinstance(payload, CatalogueState):
            previous_state = self._catalogue_state
            self._catalogue_state = payload
            self.catalogueStateChanged.emit()
            self._refresh_core_browser()
            if payload.errors and not payload.updating and (previous_state.updating or payload.errors != previous_state.errors):
                self.notice.emit("\n".join(self._error_text(error) for error in payload.errors))
        elif isinstance(payload, VersionCatalogue):
            if payload.revision < self._catalogue_state.revision:
                return
            label = self.text("cores.installed")
            choices = [{"value": core.minecraft if payload.loader == "Vanilla" else core.version, "label": core.minecraft if payload.loader == "Vanilla" else core.version, "note": label if core.installed else "", "installed": core.installed} for core in payload.cores]
            self.versionsReady.emit(payload.loader, payload.minecraft, choices)
        elif isinstance(payload, ModSearchResult):
            browser = self._mod_browsers.get(payload.build_id if payload.content_kind == 'mod' else (payload.build_id, payload.content_kind))
            if browser is not None:
                browser.accept(payload)
        elif isinstance(payload, ModProjectResult):
            for (owner, _), project in self._mod_projects.items():
                if owner == payload.build_id:
                    project.accept(payload)
            self.modTitleReady.emit(payload.build_id, payload.project_id, payload.title)
        elif isinstance(payload, ModIconResult):
            self._mod_icons[payload.project_id] = QUrl.fromLocalFile(payload.path).toString()
            for browser in self._mod_browsers.values():
                browser.model.icon_changed(payload.project_id)
            for project in self._mod_projects.values():
                if project.project_id == payload.project_id:
                    project.changed.emit()
        elif isinstance(payload, ModFiltersResult):
            browser = self._mod_browsers.get(payload.build_id if payload.content_kind == 'mod' else (payload.build_id, payload.content_kind))
            if browser is not None:
                browser.accept_filters(payload.categories)
        elif isinstance(payload, DownloadItemProgress):
            for model in self._content_queues.values():
                model.accept_progress(payload)
        elif isinstance(payload, CoreBrowseResult):
            if payload.request_id != str(self._browse_generation):
                return
            self._browse_choices = payload.cores if payload.offset == 0 else self._browse_choices + payload.cores
            versions_changed = (self._browse_versions or self._versions) != payload.minecraft_versions
            self._browse_versions = payload.minecraft_versions
            if versions_changed:
                self.coreBrowserVersionsChanged.emit()
            self._browse_more = payload.more
            self._browse_busy = False
            self._browse_task = ""
            self._browse_pages[self._browse_filter] = replace(payload, offset=0, cores=self._browse_choices[:CORE_BROWSER_FILTER_CACHE_ROWS], more=payload.more or len(self._browse_choices) > CORE_BROWSER_FILTER_CACHE_ROWS)
            self._browse_pages.move_to_end(self._browse_filter)
            while len(self._browse_pages) > CORE_BROWSER_FILTER_CACHE_ENTRIES:
                self._browse_pages.popitem(last=False)
            self._update_core_browser()
            self.coreBrowserChanged.emit()

    def _submit_mod_browser(self, command):
        return self._submit(command)

    def _cancel_mod_search(self, task):
        self._core.app.get("tasks", TaskManager).cancel(task)

    def _project(self) -> None:
        if self._batching:
            self._needs_projection = True
            return
        snapshot = self._snapshot
        if snapshot is None:
            return
        running = {key for key, item in self._clients.items() if item.state in ("starting", "running", "closing")}
        projected_builds = [BuildPreview(item.id, item.title, item.minecraft, item.loader, item.loader_version, "build.description." + item.id, index % 4, item.id in running, item.background, item.description_format, item.title_color) for index, item in enumerate(snapshot.builds)]
        builds_changed = projected_builds != self._builds
        self._builds = projected_builds
        if snapshot.builds != self._registered_builds:
            for locale in self.languages:
                entries = tuple(entry for item in snapshot.builds for entry in (("build." + item.id, item.title), ("build.description." + item.id, item.description)))
                self._router.request(Request("localization", "register", LocaleCatalog(locale, entries)))
            self._registered_builds = snapshot.builds
        previous_downloads = self._downloads
        self._downloads = []
        active = {}
        cores = {item.id: item for item in snapshot.cores}
        builds = {item.id: item for item in snapshot.builds}
        links = {**{key: ('download', '') for key, value in self._tasks.items() if value.can_retry}, **self._links}
        for task_id, (kind, owner) in links.items():
            task = self._tasks.get(task_id)
            if task_id not in self._dismissed_tasks and task and task.state in ("queued", "running", "retrying", "paused", "cancelling", "failed"):
                progress = self._task_progress(task)
                core = cores.get(owner)
                build = builds.get(owner)
                title = core.loader + " · " + core.minecraft if kind == "core" and core else self.text("editor.mods") + " · " + build.title if kind == "mod" and build else self.text("task.minecraft.resources") if kind == "resources" else task.title
                stage = self.text('downloads.stopped') if task.state == 'failed' else self._router.request(Request('localization', 'text', TextQuery('downloads.retrying', (('attempt', str(task.retry_count)), ('limit', str(task.retry_limit)))))) if task.state == 'retrying' else self._task_stage(task)
                stage_progress = int(100 * (task.stage_step + task.stage_progress) / task.stage_steps) if task.stage_progress is not None else -1
                self._downloads.append(DownloadPreview(task_id, title, progress, kind, owner, task.state == "paused", stage, stage_progress, task.bytes_per_second, task.state, self._error_text(task.error) if task.error else '', task.can_retry))
                if kind == "core" and task.state != 'failed':
                    active[owner] = (progress, task.state == "paused", stage)
        catalogue_changed = snapshot.cores != self._projected_core_source
        if catalogue_changed:
            core_choices = [CorePreview(item.id, item.minecraft, item.loader, item.version, item.installed, *active.get(item.id, (-1, False, ""))) for item in snapshot.cores]
            self._projected_core_source = snapshot.cores
            self._projected_core_indices = {item.id: index for index, item in enumerate(core_choices)}
        else:
            core_choices = self._cores.copy()
            for key in self._projected_core_active.keys() | active.keys():
                if self._projected_core_active.get(key) != active.get(key) and key in self._projected_core_indices:
                    row = self._projected_core_indices[key]
                    progress, paused, stage = active.get(key, (-1, False, ""))
                    core_choices[row] = replace(core_choices[row], progress=progress, paused=paused, stage=stage)
        self._projected_core_active = active
        if core_choices != self._cores:
            self._cores = core_choices
            if catalogue_changed:
                self._core_choices_revision += 1
                self.coreCatalogueChanged.emit()
            self.coreChoicesChanged.emit()
        installed_versions = tuple(dict.fromkeys(core.minecraft for core in self._cores if core.installed))
        if installed_versions != self._installed_core_versions:
            self._installed_core_versions = installed_versions
            self.installedCoreVersionsChanged.emit()
        minecraft_versions = tuple(dict.fromkeys(list(installed_versions) + list(self._versions)))
        if minecraft_versions != self._minecraft_versions:
            self._minecraft_versions = minecraft_versions
            self.minecraftVersionsChanged.emit()
        if self._selected and not any(item.id == self._selected for item in self._builds):
            self._selected = ""
            builds_changed = True
        if builds_changed or self._needs_general_change:
            self._needs_general_change = False
            self.changed.emit()
        else:
            self._sync_build_model()
        if previous_downloads != self._downloads:
            self.downloadsChanged.emit()

    @Slot(str, result="QVariantMap")
    def build(self, key: str) -> dict:
        value = super().build(key)
        record = next((item for item in self._snapshot.builds if item.id == key), None) if self._snapshot else None
        return {**value, **asdict(record)} if record else value

    @Slot(str, str, result=bool)
    def catalogueBusy(self, loader: str, minecraft: str) -> bool:
        return self._catalogue_state.updating or (loader, "" if loader == "Vanilla" else minecraft) in self._catalog_pending

    @Slot(str, str)
    def requestVersions(self, loader: str, minecraft: str) -> None:
        if loader == "Vanilla":
            minecraft = ""
        elif not minecraft:
            return
        if (loader, minecraft) in self._catalog_pending:
            self._catalog_again.add((loader, minecraft))
            return
        if (loader, minecraft) not in self._catalog_pending:
            self._catalog_pending.add((loader, minecraft))
            task = self._submit(ApplicationCommand("catalogue", loader, minecraft))
            self._catalog_tasks[task] = (loader, minecraft)
            self._version_catalogue_revision += 1
            self.versionCatalogueChanged.emit()

    @Slot()
    def updateCatalogue(self) -> None:
        self._submit(ApplicationCommand("update_catalogue"))

    @Slot(str, result="QVariantList")
    def editorEntries(self, key: str) -> list[dict]:
        snapshot = self._editor.get(key)
        return [asdict(item) for item in snapshot.files] if snapshot else []

    @Slot(str, result="QVariantList")
    def editorMods(self, key: str) -> list[dict]:
        snapshot = self._editor.get(key)
        root = self._core.app.get("config", CoreConfig).root
        return [{**asdict(item), "icon": QUrl.fromLocalFile(str(root / item.icon)).toString() if item.icon else ""} for item in snapshot.mods] if snapshot else []

    @Slot(str, str, str, str, str, str, str, str, str, str, str, str, result=bool)
    @Slot(str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, result=bool)
    @Slot(str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, result=bool)
    def saveBuild(self, key: str, title: str, description: str, background: str, format: str, java: str, minimum: str, maximum: str, args: str, width: str, height: str, fullscreen: str, minecraft: str = "", loader: str = "", loader_version: str = "", title_color: str | None = None) -> bool:
        fields = tuple(zip(("title", "description", "background", "description_format", "java_path", "memory_min", "memory_max", "jvm_args", "width", "height", "fullscreen"), (title, description, background, format, java, minimum, maximum, args, width, height, fullscreen)))
        if minecraft or loader:
            fields += (("minecraft", minecraft), ("loader", loader), ("loader_version", loader_version))
        if title_color is not None:
            fields += (("title_color", title_color),)
        self._submit(ApplicationCommand("update_build", key, fields=fields))
        return True

    @Slot(str, str, str)
    def importFiles(self, key: str, directory: str, urls: str) -> None:
        self._submit(ApplicationCommand("import_files", key, urls, (("directory", directory),)))

    @Slot(str, result="QVariantList")
    def editorLogs(self, key: str) -> list[dict]:
        snapshot = self._editor.get(key)
        return [asdict(item) for item in snapshot.logs] if snapshot else []

    @Slot(str, str, str, str, str, str, str, str)
    def saveBuildSettings(self, key: str, java_path: str, minimum: str, maximum: str, args: str, width: str, height: str, fullscreen: str) -> None:
        self._submit(ApplicationCommand("build_settings", key, fields=tuple(zip(("java_path", "memory_min", "memory_max", "jvm_args", "width", "height", "fullscreen"), (java_path, minimum, maximum, args, width, height, fullscreen)))))

    def handle(self, action: str, payload: object) -> object:
        if isinstance(payload, EditorCommand) and action in ("read_file", "save_file"):
            return self._submit(ApplicationCommand(action, payload.key, payload.target, (("path", payload.value),)))
        if action == "dirty":
            return super().handle(action, payload)
        if action == "create" and isinstance(payload, CreateBuildPreview):
            return self._submit(ApplicationCommand("create", payload.id, fields=(("title", payload.title), ("minecraft", payload.minecraft), ("loader", payload.loader), ("loader_version", payload.loader_version))))
        if action == "decorate" and isinstance(payload, BuildDecorationPreview):
            fields = (("title", payload.title), ("description", payload.description), ("description_format", payload.description_format), ("background", payload.background))
            if payload.title_color is not None:
                fields += (("title_color", payload.title_color),)
            self._submit(ApplicationCommand("decorate", payload.id, fields=fields))
            return True
        if action != "command" or not isinstance(payload, PreviewCommand):
            raise ValueError(action)
        command = payload
        if command.action in ("navigate", "back", "about_build", "select", "editor_dirty", "editor_save", "editor_discard", "edit"):
            if command.action == "edit":
                self._scan_editor(command.key)
            return super().handle(action, payload)
        if command.action in ("pause_download", "cancel_download", 'retry_download'):
            tasks = self._core.app.get("tasks", TaskManager)
            task_id = next((task for task, link in self._links.items() if link == ("core", command.key) and self._tasks.get(task) and self._tasks[task].state in ("queued", "running", "retrying", "paused", "cancelling")), command.key)
            if not any(task.task_id == task_id for task in tasks.snapshots()):
                return False
            task = self._tasks.get(task_id)
            if command.action == 'retry_download':
                result = tasks.retry(task_id)
                if result:
                    self._dismissed_tasks.discard(task_id)
                return result
            if command.action == "cancel_download":
                if task and task.state == 'failed':
                    self._dismissed_tasks.add(task_id)
                    self._project()
                    return True
                return tasks.cancel(task_id)
            return tasks.resume(task_id) if task and task.state == "paused" else tasks.pause(task_id)
        if command.action in ("theme", "locale"):
            service = "themes" if command.action == "theme" else "localization"
            self._router.request(Request(service, "select", command.key))
        if command.action == 'editor_scan':
            self._scan_editor(command.key)
            return True
        if command.action == "add_mod":
            return self._submit(ApplicationCommand("add_mod", command.key, command.value))
        return self._submit(ApplicationCommand(command.action, command.key, command.value, launch_origin=command.launch_origin))

    def close(self) -> None:
        self._timer.stop()
        self._editor_refresh.stop()
        paths = self._editor_watcher.directories()
        if paths:
            self._editor_watcher.removePaths(paths)
        events = self._core.app.get("events", EventManager)
        for topic in ("application", "backend", "task", "client", "core.installed", "core.browse", "core.versions", "core.catalogue", "editor", "mod_search", 'mod_project', 'mod_icon', 'mod_filters', 'mod_queue_prompt', 'mod_queue_dismissed', 'download.item'):
            events.unsubscribe(topic, self._event)
        super().close()
        self._core.close()

    def stopUpdates(self) -> None:
        self._timer.stop()

    def resumeUpdates(self) -> None:
        self._timer.start()
