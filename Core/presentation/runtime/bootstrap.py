from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from Core.configuration.settings import APP_ICON, APP_ID, APP_NAME, ASSETS_DIRECTORY, DEFAULT_LOCALE, DEFAULT_THEME, LANGUAGES_DIRECTORY, THEMES_DIRECTORY, THEME_UPDATE_SUFFIX, UI_DIRECTORY, ROOT
from Core.presentation.session import PreviewSession
from Core.presentation.live_session import LiveSession
from Core.presentation.runtime.lifecycle import LifecycleManager
from Core.application.bootstrap import create_core_runtime
from Core.application.runtime import CoreRuntime
from Core.presentation.editor.editor_workspace import EditorWorkspace
from Core.presentation.runtime.platform_identity import configure_application_identity
from Core.presentation.syntax import ConfigHighlighter, LogHighlighter
from Core.presentation.descriptions import DescriptionManager
from Core.presentation.appearance.appearance_packs import AppearancePackManager
from Core.presentation.appearance.theme_scenes import ThemeSceneManager, ThemedApplication
from Core.application.application_contracts import AppearanceScanRequest, VisualResourcesRequest
from Core.application.settings import CoreConfig
from Core.appearance.theme_health import ThemeHealth
from universal_gui.application import GuiApplication
from universal_gui.contracts import LocaleCatalog, Request
from Core.resources.runtime import register_qt_resources, resource_url
from Core.configuration.settings import UI_STYLE_DEFAULTS
from Core.application.diagnostics import messages


def create_application(preview: bool = False, core: CoreRuntime | None = None, theme: str = "", *, hardware_acceleration: bool | None = None) -> tuple[GuiApplication, PreviewSession]:
    register_qt_resources()
    backend = None if preview else core or create_core_runtime()
    packs = AppearancePackManager(None, CoreConfig(ROOT), AppearanceScanRequest("languages", (ASSETS_DIRECTORY / "locales", LANGUAGES_DIRECTORY)), AppearanceScanRequest("themes", (ASSETS_DIRECTORY / "themes", THEMES_DIRECTORY), THEME_UPDATE_SUFFIX), backend.app if backend else None)
    resources = packs.prepare(VisualResourcesRequest(ASSETS_DIRECTORY, LANGUAGES_DIRECTORY, THEMES_DIRECTORY, DEFAULT_THEME, THEME_UPDATE_SUFFIX))
    QQuickStyle.setStyle("Basic")
    configure_application_identity(APP_ID)
    preferences = packs.startupPreferences() if not preview else None
    health = packs.themeHealth() if not preview else ThemeHealth()
    if health.attempt:
        health = health.recover_interrupted(("office", "slate", "serpantine-night", "serpantine-day"))
        packs.themeHealth(health)
    acceleration = hardware_acceleration if hardware_acceleration is not None else preferences.hardware_acceleration if preferences else True
    application = ThemedApplication(APP_NAME, (ASSETS_DIRECTORY / "themes", THEMES_DIRECTORY), {"theme.initial": DEFAULT_THEME, "locale.initial": DEFAULT_LOCALE}, hardware_acceleration=acceleration)
    application.window("main", UI_DIRECTORY / "Window.qml")
    for language in resources.languages:
        application.translations(language.id, dict(language.entries))
    qt_application = QGuiApplication.instance()
    if not preview and qt_application is None:
        qt_application = QApplication([])
    runtime = application.start(preview=preview, application=qt_application)
    if resources.pending_themes:
        runtime.router.request(Request("themes", "preview_enable"))
        for pending in resources.pending_themes:
            runtime.router.request(Request("themes", "reload", pending))
    selected_theme = theme or (preferences.theme if preferences else "")
    if selected_theme in dict(health.failures):
        selected_theme = DEFAULT_THEME
    if not preview and selected_theme and ThemeSceneManager._custom(selected_theme):
        health = ThemeHealth(health.failures, selected_theme)
        packs.themeHealth(health)
    if selected_theme in runtime.router.request(Request("themes", "available")):
        runtime.router.request(Request("themes", "select", selected_theme))
    return attach_session(application, preview, backend, packs, resources, health)


def attach_session(application, preview, backend, packs, resources, health, bundle=None, *, bootstrapped=False):

    runtime = application.runtime
    runtime.engine.rootContext().setContextProperty("UiDefaults", UI_STYLE_DEFAULTS)
    runtime.engine.rootContext().setContextProperty("UiDiagnostics", messages())
    QGuiApplication.setWindowIcon(QIcon(str(APP_ICON)))
    QGuiApplication.instance().setDesktopFileName(APP_ID)
    if not ConfigHighlighter.registered:
        qmlRegisterType(ConfigHighlighter, "Launcher.Native", 1, 0, "ConfigHighlighter")
        ConfigHighlighter.registered = True
    if not LogHighlighter.registered:
        qmlRegisterType(LogHighlighter, "Launcher.Native", 1, 0, "LogHighlighter")
        LogHighlighter.registered = True
    packs.attach(runtime.router)
    if preview:
        packs.previewInstallation()
    runtime.router.register("appearance_packs", packs)
    session = PreviewSession(runtime.router) if preview else LiveSession(runtime.router, backend, bootstrapped=bootstrapped)
    packs.catalogueReady.connect(session.applyAppearanceCatalogue)
    packs.busyChanged.connect(session.appearanceRefreshChanged.emit)
    packs.themeIconsChanged.connect(session.themesChanged.emit)
    packs.libraryChanged.connect(session.styleCatalogueChanged.emit)
    packs.themeInstalled.connect(session.styleInstalled)
    packs.attachThemeDrops(session.importThemes)
    packs.failed.connect(session.appearanceRefreshFailed)
    runtime.router.register("launcher_preview", session)
    runtime.router.register("descriptions", DescriptionManager())
    editors = EditorWorkspace(runtime.router, runtime.engine)
    editors.attach(session)
    runtime.router.register("editor_workspace", editors)
    lifecycle = LifecycleManager(session, backend, editors)
    runtime.router.register("lifecycle", lifecycle)
    runtime.engine.addImportPath(str(UI_DIRECTORY))
    runtime.engine.rootContext().setContextProperty("Session", session)
    runtime.engine.rootContext().setContextProperty("Editors", editors)
    runtime.engine.rootContext().setContextProperty("Lifecycle", lifecycle)
    runtime.engine.rootContext().setContextProperty("IconSources", {name: resource_url(path) for name, path in resources.icons})
    runtime.engine.rootContext().setContextProperty("ImageFiles", {name: resource_url(path) for name, path in resources.images})
    scenes = ThemeSceneManager(runtime.router, runtime.engine, packs, session, editors, lifecycle, health, persistent=not preview)
    runtime.router.register("theme_scenes", scenes)
    runtime.engine.rootContext().setContextProperty("ThemeUI", scenes)
    scenes.initialize(bundle)
    build_captions = tuple(("build." + build["id"], build["title"]) for build in session.builds)
    for locale in session.languages:
        runtime.router.request(Request("localization", "register", LocaleCatalog(locale, build_captions)))
    return application, session
