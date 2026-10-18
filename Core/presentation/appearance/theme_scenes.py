from Core.application.diagnostics import diagnostic
from pathlib import Path
import json

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtQml import QQmlComponent
from shiboken6 import isValid

from Core.configuration.settings import UI_DIRECTORY, DEFAULT_THEME, THEME_SETTLE_INTERVAL_MS, THEME_SCENE_BYTES, THEME_FAILURE_DETAIL_LENGTH
from Core.appearance.theme_health import ThemeHealth
from Core.appearance.theme_scenes import ThemeSceneBundle, ThemeSceneRequest, scene_configuration
from universal_gui.contracts import AssetQuery, Diagnostic, Request, WindowDefinition
from universal_gui.services.events import Subscription
from universal_gui.runtime import PACKAGE_ROOT
from universal_gui.application import GuiApplication
from Core.resources.runtime import resource_url


class ThemeSceneManager(QObject):
    changed = Signal()
    mainSceneChanged = Signal()

    retryRequested = Signal(str, str)

    def __init__(self, router, engine, packs, session, editors, lifecycle, health=ThemeHealth(), persistent=True) -> None:
        super().__init__()
        self._router = router
        self._engine = engine
        self._packs = packs
        self._session = session
        self._editors = editors
        self._lifecycle = lifecycle
        self._base_imports = engine.importPathList()
        self._bundle = ThemeSceneBundle("", None, "")
        self._pending = None
        self._busy = False
        self._again = False
        self._error = ""
        self._closed = False
        self._resource_revision = 0
        self._saved_main_state = {}
        self._failures = dict(health.failures)
        self._attempt = health.attempt
        self._persistent = persistent
        self._retry_theme = ""
        self._fault = None
        self._preparing_theme = ""
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.setInterval(THEME_SETTLE_INTERVAL_MS)
        self._settle_timer.timeout.connect(self._settle)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._prepare)
        self._subscription = router.request(Request("events", "subscribe", Subscription("theme.changed", self._theme_changed)))
        self._visual_subscription = router.request(Request("events", "subscribe", Subscription("visual.failed", self._visual_failed)))
        engine.warnings.connect(self._qml_errors)
        packs.scenesReady.connect(self._ready)
        packs.scenesFailed.connect(self._failed)
        editors.changed.connect(self._apply_pending)
        lifecycle.shutdownStarted.connect(self._prepare_shutdown)

    busy = Property(bool, lambda self: self._busy, notify=changed)
    pending = Property(bool, lambda self: self._pending is not None, notify=changed)
    appliedTheme = Property(str, lambda self: self._bundle.theme_id, notify=changed)
    lastError = Property(str, lambda self: self._error, notify=changed)
    apiVersion = Property(int, lambda self: 1, constant=True)
    resourceRevision = Property(int, lambda self: self._resource_revision, notify=changed)
    failedThemes = Property("QVariantMap", lambda self: dict(self._failures), notify=changed)

    @staticmethod
    def _custom(theme):
        return bool(theme) and theme not in ("office", "slate", "serpantine-night", "serpantine-day")

    def _save_health(self):
        if self._persistent:
            try:
                self._packs.themeHealth(ThemeHealth(tuple(self._failures.items()), self._attempt))
            except (OSError, ValueError) as error:
                self._router.request(Request("diagnostics", "record", Diagnostic("WARNING", "launcher.theme_health", str(error))))

    @Slot(str)
    def requestTheme(self, theme):
        if self._closed:
            return
        if theme in self._failures:
            self._retry_theme = theme
            self.retryRequested.emit(theme, self._failures[theme])
            return
        self._activate(theme)

    @Slot(bool)
    def resolveThemeRetry(self, accepted):
        if self._closed:
            return
        theme, self._retry_theme = self._retry_theme, ""
        if accepted and theme:
            self._failures.pop(theme, None)
            self.changed.emit()
            self._activate(theme)

    def _activate(self, theme):
        if self._closed:
            return
        self._attempt = theme if self._custom(theme) else ""
        self._save_health()
        try:
            self._session.command("theme", theme)
        except (ValueError, KeyError, OSError) as error:
            self._reject(theme, str(error))
        self._settle_timer.start()

    def _settle(self):
        if self._closed or self._fault:
            return
        window = self._router.request(Request("windows", "instance", "main"))
        if self._busy or window is None or not isValid(window) or not window.property("startupComplete"):
            self._settle_timer.start()
            return
        self._attempt = ""
        self._save_health()

    def _owns_url(self, url, theme):
        if str(url).startswith("qrc:/ugpack/" + theme + "/"):
            return True
        if self._bundle.theme_id != theme or self._bundle.directory is None:
            return False
        path = Path(QUrl(url).toLocalFile())
        for kind, entries in (("views", self._bundle.views), ("framework", self._bundle.framework_views)):
            if any(path == self._bundle.directory / kind / key for key in entries):
                return True
        return False

    def _qml_errors(self, errors):
        if self._closed:
            return
        theme = self._session.theme
        if self._custom(theme):
            owned = [error.toString() for error in errors if self._owns_url(error.url().toString(), theme)
                     and any(marker in error.description() for marker in ("Error", "Cannot assign", "is not defined", "is not a function"))]
            if owned:
                self._queue_fault(theme, "\n".join(owned))

    def _visual_failed(self, event):
        theme = event.payload.source.split("/", 1)[0]
        if theme == self._session.theme and self._custom(theme):
            self._queue_fault(theme, event.payload.detail)

    def _queue_fault(self, theme, message):
        if self._fault is None:
            self._fault = theme, message
            QTimer.singleShot(0, self._recover_fault)

    def _recover_fault(self):
        fault, self._fault = self._fault, None
        if not self._closed and fault and fault[0] == self._session.theme:
            self._reject(*fault)

    def _reject(self, theme, message):
        if not self._custom(theme):
            return
        self._failures[theme] = message[:THEME_FAILURE_DETAIL_LENGTH]
        self._attempt = ""
        self._save_health()
        self._error = message
        self.changed.emit()
        if self._session.theme == theme:
            self._session.command("theme", DEFAULT_THEME)
        self._session.notice.emit(self._session.text("theme.disabled") + " " + theme)

    def initialize(self, prepared_bundle=None) -> None:
        self._preparing_theme = self._session.theme
        try:
            if prepared_bundle is None:
                request = self._snapshot()
                self._preparing_theme = request.theme_id
                bundle = self._packs.prepareScenes(request, immediate=True) if request.resources else ThemeSceneBundle(request.theme_id, None, "")
            else:
                bundle = prepared_bundle
            self._apply(bundle)
            self._settle_timer.start()
        except Exception as error:
            self._failed(str(error))

    def _snapshot(self) -> ThemeSceneRequest:
        manifest = self._router.request(Request("themes", "inspect"))
        theme_id = manifest["id"]
        roots = scene_configuration(manifest)
        resources = []
        total = 0
        if any(roots):
            for key in self._router.request(Request("resources", "keys", theme_id)):
                if not any(root and key.startswith(root + "/") for root in roots):
                    continue
                content = self._router.request(Request("resources", "read", AssetQuery(theme_id, key))).content
                total += len(content)
                if total > THEME_SCENE_BYTES:
                    raise ValueError(diagnostic('theme_scenes.launcher.scene.resources.exceed.mib'))
                resources.append((key, content))
        return ThemeSceneRequest(theme_id, UI_DIRECTORY, PACKAGE_ROOT / "qml", json.dumps(manifest).encode(), tuple(resources))

    def _theme_changed(self, event) -> None:
        if self._closed:
            return
        if self._session.theme in self._failures:
            self._session.command("theme", DEFAULT_THEME)
            return
        self._preparing_theme = self._session.theme
        try:
            manifest = self._router.request(Request("themes", "inspect"))
            if scene_configuration(manifest)[1]:
                bundle = self._packs.prepareScenes(self._snapshot(), immediate=True)
                self._engine.addImportPath(str(bundle.directory / "framework"))
        except Exception as error:
            self._failed(str(error))
            return
        self._attempt = self._session.theme if self._custom(self._session.theme) else ""
        self._save_health()
        self._settle_timer.start()
        self._resource_revision += 1
        self.changed.emit()
        self._timer.start(0)

    @Slot()
    def _prepare(self) -> None:
        if self._closed:
            return
        if self._busy:
            self._again = True
            return
        self._error = ""
        self._preparing_theme = self._session.theme
        try:
            request = self._snapshot()
            self._preparing_theme = request.theme_id
            if not request.resources:
                self._ready(ThemeSceneBundle(request.theme_id, None, ""))
                return
            self._busy = True
            self.changed.emit()
            self._packs.prepareScenes(request)
        except Exception as error:
            self._failed(str(error))

    @Slot(object)
    def _ready(self, bundle: ThemeSceneBundle) -> None:
        if self._closed:
            return
        self._busy = False
        if self._again or bundle.theme_id != self._session.theme:
            self._again = False
            self._timer.start(0)
            self.changed.emit()
            return
        if bundle.signature != self._bundle.signature and self._editors.windowKeys and bundle.theme_id != DEFAULT_THEME:
            self._pending = bundle
            self._session.notice.emit(self._session.text("theme.views_pending"))
            self.changed.emit()
            return
        self._apply(bundle)

    @Slot()
    def _apply_pending(self) -> None:
        if self._pending is not None and not self._editors.windowKeys and not self._busy:
            bundle = self._pending
            self._pending = None
            if bundle.theme_id == self._session.theme:
                QTimer.singleShot(0, self._apply_pending_bundle)
                self._pending = bundle

    def _apply_pending_bundle(self) -> None:
        if self._pending is not None and not self._editors.windowKeys and self._pending.theme_id == self._session.theme:
            self._apply(self._pending)

    def _apply(self, bundle: ThemeSceneBundle) -> None:
        previous = self._bundle
        if bundle.signature == previous.signature:
            self._bundle = bundle
            self._pending = None
            self.changed.emit()
            main = self._router.request(Request("windows", "instance", "main"))
            if main is not None and main.property("mainContent") is None:
                self.mainSceneChanged.emit()
            return
        self._map(bundle)
        self._bundle = bundle
        self._engine.trimComponentCache()
        try:
            main = self._router.request(Request("windows", "instance", "main"))
            if main is not None:
                self._main_state(main)
            else:
                self._router.request(Request("windows", "configure", WindowDefinition("main", str(UI_DIRECTORY / "Window.qml"))))
            self._editors.clearViewCache()
        except Exception as error:
            self._map(previous)
            self._bundle = previous
            self._engine.trimComponentCache()
            self._failed(str(error), theme_failure=isinstance(error, (ValueError, KeyError, OSError)))
            return
        self._bundle = bundle
        self._pending = None
        self.changed.emit()
        self.mainSceneChanged.emit()

    @Slot(str)
    def mainFailed(self, message):
        self._preparing_theme = self._session.theme
        self._failed(message)

    @Slot(str, str)
    def rejectTheme(self, theme, message):
        self._reject(theme, message)

    def _map(self, bundle: ThemeSceneBundle) -> None:
        paths = []
        if bundle.views:
            paths.append(str(bundle.directory / "views"))
        if bundle.framework_views:
            paths.append(str(bundle.directory / "framework"))
        self._engine.setImportPathList(paths + self._base_imports)
        framework = bundle.directory / "framework" if bundle.framework_views else PACKAGE_ROOT / "qml"
        self._router.request(Request("windows", "scene_root", framework))

    def _main_state(self, window) -> tuple:
        keys = {"page.builds": ("search", "filterId", "filterMinecraft", "filterLoader", "filterLoaderVersion", "filterState"), "page.settings": ("section",), "page.cores": ("minecraft", "loader", "filter")}
        values = []
        for name, properties in keys.items():
            item = window.findChild(QObject, name)
            if item is not None:
                record = tuple((key, item.property(key)) for key in properties if item.metaObject().indexOfProperty(key) >= 0)
                self._saved_main_state[name] = record
                values.append((name, record))
        return tuple(values)

    def _restore_main_state(self, window, state: tuple) -> None:
        for name, properties in state:
            item = window.findChild(QObject, name)
            if item is not None:
                for key, value in properties:
                    if item.metaObject().indexOfProperty(key) >= 0:
                        item.setProperty(key, value)

    @Slot(QObject, str)
    def restorePageState(self, page: QObject, name: str) -> None:
        for key, value in self._saved_main_state.get(name, ()):
            if page.metaObject().indexOfProperty(key) >= 0:
                page.setProperty(key, value)

    @Slot(str, result=str)
    def assetUrl(self, key: str) -> str:
        return self._router.request(Request("themes", "asset_url", AssetQuery(self._session.theme, key)))

    @Slot(str, result=str)
    def viewUrl(self, key: str) -> str:
        from_root = self._bundle.directory / "views" if self._bundle.views else UI_DIRECTORY
        return resource_url(from_root / key)

    @Slot(str)
    def _failed(self, message: str, theme_failure=True) -> None:
        if self._closed:
            return
        self._busy = False
        self._pending = None
        self._error = message
        self._router.request(Request("diagnostics", "record", Diagnostic("ERROR", "launcher.theme_scene", message)))
        self._session.notice.emit(self._session.text("theme.views_failed") + " " + message)
        self.changed.emit()
        if theme_failure and self._custom(self._preparing_theme) and self._preparing_theme == self._session.theme:
            self._reject(self._preparing_theme, message)
        if self._again:
            self._again = False
            self._timer.start(0)

    def handle(self, action: str, payload):
        if action == "status":
            return self._bundle
        if action == "view_url":
            return self.viewUrl(payload)
        if action == "reset":
            if not self._bundle.signature:
                return False
            fallback = ThemeSceneBundle(self._session.theme, None, "")
            self._map(fallback)
            self._bundle = fallback
            self._engine.trimComponentCache()
            self._editors.clearViewCache()
            if self._router.request(Request("windows", "instance", "main")) is None:
                self._router.request(Request("windows", "configure", WindowDefinition("main", str(UI_DIRECTORY / "Window.qml"))))
            else:
                self.mainSceneChanged.emit()
            self._failed(str(payload))
            return True
        raise ValueError(action)

    def _prepare_shutdown(self) -> None:
        self._closed = True
        self._timer.stop()
        self._settle_timer.stop()
        if self._attempt:
            self._attempt = ""
            self._save_health()

    def close(self) -> None:
        if self._engine is None:
            return
        self._prepare_shutdown()
        self._router.request(Request("events", "unsubscribe", self._subscription))
        self._router.request(Request("events", "unsubscribe", self._visual_subscription))
        if isValid(self._engine):
            self._engine.warnings.disconnect(self._qml_errors)
        self._engine = None


class ThemedApplication(GuiApplication):
    def open_window(self, key: str) -> None:
        try:
            super().open_window(key)
        except ValueError as error:
            if key != "main" or not self.runtime.router.request(Request("theme_scenes", "reset", str(error))):
                raise
            super().open_window(key)
        if key == "main":
            self.runtime.router.request(Request("windows", "instance", key)).setObjectName("launcher.main")
