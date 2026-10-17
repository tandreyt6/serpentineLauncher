from Core.application.diagnostics import diagnostic
from concurrent.futures import TimeoutError
from zlib import error as CompressionError
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QObject, QTimer, Signal

from Core.configuration.settings import BACKEND_EVENT_INTERVAL_MS, APPLICATION_STATE_FILENAME
from Core.application.application_contracts import AppearanceCatalogue, AppearanceScanRequest, ThemeFile, VisualResources, VisualResourcesRequest
from Core.appearance.appearance_packs import AppearanceFileDriver, AppearanceScanOperation, VisualResourcesOperation
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.tasks import TaskManager
from Core.appearance.theme_scenes import StartupPreferencesOperation, ThemeSceneDriver, ThemeSceneOperation, ThemeSceneRequest
from Core.appearance.theme_health import ThemeHealthDriver, ThemeHealthOperation
from Core.appearance.theme_installation import ThemeInstallOperation
from Core.presentation.appearance.theme_icons import load_theme_icons
from Core.resources.runtime import ResourcePath
from universal_gui.contracts import AssetQuery, LocaleCatalog, Request


class AppearancePackManager(QObject):
    catalogueReady = Signal(AppearanceCatalogue)
    busyChanged = Signal()
    failed = Signal(str)
    scenesReady = Signal(object)
    scenesFailed = Signal(str)
    themeIconsChanged = Signal()
    libraryChanged = Signal()
    themeInstalled = Signal(str)

    def __init__(self, router, config: CoreConfig, languages: AppearanceScanRequest, themes: AppearanceScanRequest, app: AppManager | None = None, scene_driver=None) -> None:
        super().__init__()
        self._router = router
        self._requests = {"languages": languages, "themes": themes}
        self._owns_app = app is None
        self._app = app or AppManager()
        self._config = config
        self._health = ThemeHealthDriver(config.root)
        self._theme_icons = {}
        self._icon_errors = {}
        self._library_error = ''
        self._import_serial = 0
        self._preview_installation = None
        self._drop_filter = None
        if self._owns_app:
            self._app.register("events", EventManager())
            self._app.register("appearance_files", AppearanceFileDriver(config))
            self._app.register("tasks", TaskManager(self._app, 1))
        try:
            self._app.get("theme_scenes", ThemeSceneDriver)
        except KeyError:
            self._app.register("theme_scenes", scene_driver or ThemeSceneDriver())
        self._pending: dict[str, str] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(BACKEND_EVENT_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def handle(self, action: str, payload: object) -> object:
        if action == 'theme_library':
            rows = []
            for identity in self._router.request(Request('themes', 'available')):
                if identity in ('office', 'slate'):
                    continue
                manifest = json.loads(self._router.request(Request('resources', 'read', AssetQuery(identity, 'manifest.json'))).content)
                title = manifest.get('name', identity)
                rows.append(dict(id=identity, title=title if isinstance(title, str) else identity,
                                 icon=self._theme_icons.get(identity, ''), error=self._icon_errors.get(identity, ''), builtin=identity in ('serpantine-night', 'serpantine-day')))
            return sorted(rows, key=lambda row: (not row['builtin'], row['title'].casefold(), row['id']))
        if action == 'library_error':
            return self._library_error
        if action == 'import_themes':
            self._library_error = ''
            tasks = self._app.get('tasks', TaskManager)
            request = self._requests['themes']
            destination = request.directories[-1]
            for source in payload:
                self._import_serial += 1
                operation = ThemeInstallOperation(self._config, source, destination, request)
                self._pending['install:' + str(self._import_serial)] = tasks.submit('Install theme', operation.run, queue='files')
            self.libraryChanged.emit()
            self.busyChanged.emit()
            self._timer.start()
            return None
        if action == 'theme_icons':
            return dict(self._theme_icons)
        if action == "busy":
            return tuple(self._pending)
        if action == "refresh" and payload in self._requests:
            if payload not in self._pending:
                if payload == 'themes':
                    self._library_error = ''
                    self.libraryChanged.emit()
                self._pending[payload] = self._app.get("tasks", TaskManager).submit("Refresh " + payload, AppearanceScanOperation(self._app, self._requests[payload]).run)
                self.busyChanged.emit()
                self._timer.start()
            return None
        raise ValueError(diagnostic('appearance_packs.unknown.appearance.pack.request'))

    def attach(self, router) -> None:
        self._router = router
        self._load_theme_icons()

    def previewInstallation(self):
        self._preview_installation = TemporaryDirectory(prefix='launcher-preview-themes-')
        request = self._requests['themes']
        self._requests['themes'] = AppearanceScanRequest('themes', request.directories + (Path(self._preview_installation.name),), request.pending_suffix)

    def attachThemeDrops(self, install):
        from Core.presentation.appearance.theme_drop import ThemeDropFilter
        self._drop_filter = ThemeDropFilter(install, self)

    def _load_theme_icons(self):
        self._icon_errors = {}
        icons = load_theme_icons(self._router, self._icon_errors)
        if icons != self._theme_icons:
            self._theme_icons = icons
            self.themeIconsChanged.emit()

    def prepare(self, request: VisualResourcesRequest) -> VisualResources:
        tasks = self._app.get("tasks", TaskManager)
        task = tasks.submit("Prepare visual resources", VisualResourcesOperation(self._app, request).run)
        try:
            return tasks.wait(task)
        finally:
            tasks.release(task)

    def startupPreferences(self):
        tasks = self._app.get("tasks", TaskManager)
        task = tasks.submit("Read startup preferences", StartupPreferencesOperation(self._app, self._config.root, APPLICATION_STATE_FILENAME, self._config.appearance_index_bytes).run)
        try:
            return tasks.wait(task)
        finally:
            tasks.release(task)

    def themeHealth(self, snapshot=None):
        tasks = self._app.get("tasks", TaskManager)
        task = tasks.submit("Theme health", ThemeHealthOperation(self._health, snapshot).run)
        try:
            return tasks.wait(task)
        finally:
            tasks.release(task)

    def prepareScenes(self, request: ThemeSceneRequest, immediate: bool = False):
        tasks = self._app.get("tasks", TaskManager)
        task = tasks.submit("Prepare theme scenes", ThemeSceneOperation(self._app, request).run)
        if immediate:
            try:
                return tasks.wait(task)
            finally:
                tasks.release(task)
        self._pending["scenes:" + task] = task
        self._timer.start()
        return None

    def _poll(self) -> None:
        tasks = self._app.get("tasks", TaskManager)
        for kind, task in tuple(self._pending.items()):
            try:
                catalogue = tasks.wait(task, 0)
            except TimeoutError:
                continue
            except Exception as error:
                self._library_error = str(error)
                self.libraryChanged.emit()
                if kind.startswith("scenes:"):
                    self.scenesFailed.emit(str(error))
                else:
                    self.failed.emit(str(error))
            else:
                if kind.startswith('install:'):
                    accepted = self._apply(catalogue.catalogue)
                    if any(theme.id == catalogue.id and theme.path == catalogue.path for theme in accepted):
                        for obsolete in catalogue.obsolete:
                            try:
                                obsolete.unlink(missing_ok=True)
                            except OSError:
                                pass
                        self.themeInstalled.emit(catalogue.id)
                    else:
                        catalogue.path.unlink(missing_ok=True)
                elif kind.startswith("scenes:"):
                    self.scenesReady.emit(catalogue)
                else:
                    self._apply(catalogue)
            del self._pending[kind]
            tasks.release(task)
            self.busyChanged.emit()
        self._app.get("events", EventManager).drain()
        if not self._pending:
            self._timer.stop()

    def _apply(self, catalogue: AppearanceCatalogue) -> None:
        if catalogue.kind == "languages":
            for language in catalogue.languages:
                self._router.request(Request("localization", "register", LocaleCatalog(language.id, language.entries)))
            self.catalogueReady.emit(catalogue)
        else:
            accepted = []
            self._router.request(Request("themes", "preview_enable"))
            for theme in catalogue.themes:
                previous = self._router._departments['resources']._packs.get(theme.id)
                try:
                    self._router.request(Request("themes", "reload", theme.path))
                except (OSError, ValueError, KeyError, CompressionError) as error:
                    self._library_error = f"{theme.path.name}: {error}"
                    self.failed.emit(f"{theme.path.name}: {error}")
                    if previous is not None and previous.path != theme.path:
                        accepted.append(ThemeFile(theme.id, previous.path))
                else:
                    accepted.append(theme)
            self._load_theme_icons()
            self.catalogueReady.emit(AppearanceCatalogue("themes", themes=tuple(accepted)))
            self.libraryChanged.emit()
        if catalogue.errors:
            self._library_error = '\n'.join(catalogue.errors)
            self.libraryChanged.emit()
            self.failed.emit("\n".join(catalogue.errors))
        return tuple(accepted) if catalogue.kind == 'themes' else ()

    def close(self) -> None:
        if self._drop_filter:
            self._drop_filter.close()
        self._timer.stop()
        if self._owns_app:
            self._app.get("tasks", TaskManager).close()
            self._app.get("events", EventManager).close()
        self._app.get("theme_scenes", ThemeSceneDriver).close()
        if self._preview_installation:
            resources = self._router._departments.get('resources')
            if resources:
                directory = Path(self._preview_installation.name)
                for identity, pack in tuple(resources._packs.items()):
                    if not isinstance(pack.path, ResourcePath) and pack.path.resolve().is_relative_to(directory):
                        resources.handle('unmount', identity)
            self._preview_installation.cleanup()
        for signal in (self.catalogueReady, self.busyChanged, self.failed):
            try:
                signal.disconnect()
            except RuntimeError:
                pass
