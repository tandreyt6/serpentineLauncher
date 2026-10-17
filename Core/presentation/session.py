from Core.application.diagnostics import diagnostic
from dataclasses import asdict, replace
import re

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot, QLocale

from Core.configuration.settings import APP_VERSION, DEFAULT_LOCALE, DEFAULT_THEME, MINIMUM_MEMORY_MB, PREVIEW_MEMORY_LIMIT_MB, APPLICATION_SETTING_CHOICES, APPLICATION_SETTING_RANGES, UI_RUNTIME_SETTINGS, BUILTIN_LOCALE, DEFAULT_GAME_WINDOW_WIDTH, DEFAULT_GAME_WINDOW_HEIGHT, MINIMUM_GAME_WINDOW_WIDTH, MINIMUM_GAME_WINDOW_HEIGHT, MAXIMUM_GAME_WINDOW_DIMENSION, DEFAULT_BUILD_TITLE_COLOR, MEBIBYTE_BYTES
from Core.application.application_contracts import AppearanceCatalogue, ModCatalogEntry, ModSearchResult, ModProjectResult, ModVersionEntry, ApplicationCommand
from Core.presentation.catalog.mod_browser import ModBrowser
from Core.presentation.catalog.mod_project import ModProject
from Core.presentation.catalog.content_queue import ContentQueueModel
from Core.presentation.editor.editor_mods import EditorModsModel
from Core.presentation.contracts import AccountPreview, BuildCorePreview, BuildDecorationPreview, BuildPreview, CardSizeOption, CorePreview, CreateBuildPreview, DescriptionDocument, DownloadPreview, EditorCommand, PreviewCommand, SettingChoice
from Core.presentation.fixtures import ACCOUNTS, BUILDS, CORES, MOD_CATALOG, SETTINGS
from Core.presentation.build_model import BuildListModel, CoreListModel, DownloadListModel
from Core.presentation import shortcuts
from Core.configuration.settings import SHORTCUT_ACTIONS
from Core.content.versions import version_key
from universal_gui.contracts import Event, LocaleCatalog, Request, SettingChange, TextQuery
from universal_gui.services.events import Subscription


class PreviewSession(QObject):
    cardSizeOptions = Property("QVariantList", lambda self: [asdict(CardSizeOption(key, "builds." + key, key + "CardWidth")) for key in APPLICATION_SETTING_CHOICES["buildCardSize"]], constant=True)
    buildDoubleClickOptions = Property("QVariantList", lambda self: [asdict(SettingChoice(key, "settings.build_double_click." + key)) for key in APPLICATION_SETTING_CHOICES["buildDoubleClickAction"]], constant=True)
    changed = Signal()
    downloadsChanged = Signal()
    localeChanged = Signal()
    themeChanged = Signal()
    notice = Signal(str)
    editorSaveRequested = Signal(str)
    editorDiscardRequested = Signal(str)
    coreBrowserChanged = Signal()
    coreBrowserVersionsChanged = Signal()
    coreChoicesChanged = Signal()
    coreCatalogueChanged = Signal()
    minecraftVersionsChanged = Signal()
    installedCoreVersionsChanged = Signal()
    buildCoreChanged = Signal()
    languagesChanged = Signal()
    themesChanged = Signal()
    styleCatalogueChanged = Signal()
    appearanceRefreshChanged = Signal()
    versionCatalogueChanged = Signal()
    catalogueStateChanged = Signal()
    versionsReady = Signal(str, str, "QVariantList")
    modTitleReady = Signal(str, str, str)
    modQueueDecision = Signal('QVariantMap')
    modQueueDecisionDismissed = Signal(str, str)
    firstRunChanged = Signal()

    @Slot(str, str, str)
    def resolveModQueue(self, build_id, request_id, choice):
        if not self._closing:
            self._submit_mod_browser(ApplicationCommand('resolve_mod_queue', build_id, request_id, (('choice', choice),)))

    def __init__(self, router, demo: bool = True) -> None:
        super().__init__()
        self._closing = False
        self._first_run_setup = None
        self._first_run_requested = False
        self._router = router
        self._builds = list(BUILDS) if demo else []
        self._build_model = BuildListModel(BUILDS if demo else (), self)
        self._build_core_states: dict[str, BuildCorePreview] = {}
        self._build_core_revision = 0
        self.changed.connect(self._sync_build_model)
        self._accounts = list(ACCOUNTS) if demo else []
        self._cores = list(CORES) if demo else []
        self._core_browser_model = CoreListModel(self)
        self._core_choices_revision = 0
        self._mod_queue = []
        self._mod_browsers: dict[str, ModBrowser] = {}
        self._mod_projects = {}
        self._mod_icons = {}
        self._content_queues = {}
        self._editor_mod_models = {}
        self.editorChanged.connect(self._sync_editor_mod_models)
        self.changed.connect(self._sync_content_queues)
        self._downloads = [DownloadPreview(core.id, core.loader + " · " + core.minecraft, core.progress, "core", core.id) for core in CORES if core.progress >= 0] if demo else []
        self._download_model = DownloadListModel(self)
        self.changed.connect(self._sync_download_model)
        self.changed.connect(self.downloadsChanged.emit)
        self.downloadsChanged.connect(self._sync_download_model)
        self._settings = dict(SETTINGS)
        self._page = "builds"
        self._page_history: list[str] = []
        self._about_build = ""
        self._selected = ""
        self._account = "alex" if demo else ""
        self._revision = 0
        self._version_catalogue_revision = 0
        self._language_ids = None
        self._theme_ids = None
        self._style_selection = ''
        self._dirty_editors: set[str] = set()
        self._subscriptions = [router.request(Request("events", "subscribe", Subscription("locale.changed", self._locale_changed))), router.request(Request("events", "subscribe", Subscription("theme.changed", self._theme_changed)))]
        self._sync_build_model()
        self._sync_download_model()
        self._sync_presentation_settings()

    firstRunPending = Property(bool, lambda self: self._first_run_setup is not None, notify=firstRunChanged)
    firstRunJavaFound = Property(bool, lambda self: self._first_run_setup is not None and self._first_run_setup.java_found, notify=firstRunChanged)

    @Slot()
    def prepareFirstRun(self):
        return None

    @Slot()
    def acknowledgeFirstRun(self):
        self._first_run_setup = None
        self.firstRunChanged.emit()

    def _sync_presentation_settings(self) -> None:
        for source, destination, kind in UI_RUNTIME_SETTINGS:
            self._router.request(Request("settings", "set", SettingChange(destination, kind(self._settings[source]))))

    @Slot(str, result=QObject)
    @Slot(str, str, result=QObject)
    def modBrowser(self, key: str, content_kind='mod'):
        identity = key if content_kind == 'mod' else (key, content_kind)
        if identity not in self._mod_browsers:
            build = self.build(key)
            browser = ModBrowser(key, self._submit_mod_browser, lambda: self._mod_queue, self._cancel_mod_search, self, self._mod_icons, (build.get('minecraft', ''), build.get('loader', '').lower() if content_kind == 'mod' else ''), content_kind, self.contentQueue(key, content_kind), translate=self.text)
            self._mod_browsers[identity] = browser
            self.changed.connect(browser.queueChanged)
            self.localeChanged.connect(browser.changed)
        return self._mod_browsers[identity]

    @Slot(str, str, result=QObject)
    def contentQueue(self, build_id, content_kind):
        key = (build_id, content_kind)
        if key not in self._content_queues:
            model = ContentQueueModel(build_id, content_kind, self)
            model.synchronize(self._mod_queue)
            self._content_queues[key] = model
        return self._content_queues[key]

    def _sync_content_queues(self):
        for model in self._content_queues.values():
            model.synchronize(self._mod_queue)

    @Slot(str, str, result=QObject)
    @Slot(str, str, str, result=QObject)
    def modProject(self, build_id, project_id, content_kind='mod'):
        key = (build_id, project_id if content_kind == 'mod' else content_kind + ':' + project_id)
        if key not in self._mod_projects:
            browser = self.modBrowser(build_id, content_kind)
            project = ModProject(build_id, project_id, self._submit_mod_browser, lambda: self._mod_queue, self._mod_icons, self, (browser.minecraft, browser.loader), content_kind, translate=self.text)
            self._mod_projects[key] = project
            self.changed.connect(project.queueChanged)
            self.localeChanged.connect(project.changed)
            browser.filtersChanged.connect(project.setCatalogFilters)
        return self._mod_projects[key]

    @Slot(str, str, str)
    def applyCatalogFilters(self, build_id, project_id, content_kind):
        browser = self.modBrowser(build_id, content_kind)
        self.modProject(build_id, project_id, content_kind).setCatalogFilters(browser.minecraft, browser.loader)

    @Slot(str, str)
    @Slot(str, str, str)
    def releaseModProject(self, build_id, project_id, content_kind='mod'):
        project = self._mod_projects.pop((build_id, project_id if content_kind == 'mod' else content_kind + ':' + project_id), None)
        if project is not None:
            project.deleteLater()

    def _cancel_mod_search(self, task):
        pass

    def _submit_mod_browser(self, command):
        if command.action == "mod_search":
            fields = dict(command.fields)
            kind = fields.get('content_kind', 'mod')
            identity = command.key if kind == 'mod' else (command.key, kind)
            entries = tuple(ModCatalogEntry(item.id, item.title, item.source, command.key) for item in MOD_CATALOG if kind == 'mod' and command.value.casefold() in item.title.casefold())
            offset, limit = int(fields["offset"]), int(fields["limit"])
            page = entries[offset:offset + limit]
            result = ModSearchResult(command.key, page, fields["request_id"], offset, offset + len(page), offset + len(page) < len(entries), kind)
            QTimer.singleShot(0, self._mod_browsers[identity], lambda: self._mod_browsers[identity].accept(result))
        elif command.action == 'mod_project':
            kind = dict(command.fields).get('content_kind', 'mod')
            identity = (command.key, command.value if kind == 'mod' else kind + ':' + command.value)
            item = next((item for item in MOD_CATALOG if item.id == command.value), None)
            build = self.build(command.key)
            target = ((build.get('minecraft', ''),), (build.get('loader', '').lower(),))
            result = ModProjectResult(command.key, dict(command.fields)['request_id'], command.value, item.title if item else command.value, 'Preview description', '# Mod description\n\nA local preview of the mod page.', '', (ModVersionEntry('preview-old', '1.0', 'Version 1.0', 'release', '2025-01-01', 'mod.jar', 10, *target), ModVersionEntry('preview-new', '2.0', 'Version 2.0', 'beta', '2026-01-01', 'mod.jar', 20, *target)), kind)
            def accept_project():
                self._mod_projects[identity].accept(result)
                self.modTitleReady.emit(command.key, command.value, result.title)
            QTimer.singleShot(0, self._mod_projects[identity], accept_project)
        elif command.action in ('mod_filters', 'mod_icons'):
            return ''
        else:
            value = dict(command.fields).get("id", command.value)
            self.handle("command", PreviewCommand(command.action, command.key, value))
            if command.action == 'add_mod' and dict(command.fields).get('version_id'):
                version = dict(command.fields)['version_id']
                self._mod_queue = [replace(item, version_id=version, version_number='1.0' if version == 'preview-old' else '2.0') if item.owner_id == command.key and item.id == value else item for item in self._mod_queue]
                self.changed.emit()
        return ""

    version = Property(str, lambda self: APP_VERSION, constant=True)
    builds = Property("QVariantList", lambda self: [asdict(build) for build in self._builds], notify=changed)
    buildModel = Property(QObject, lambda self: self._build_model, constant=True)
    accounts = Property("QVariantList", lambda self: [asdict(account) for account in self._accounts], notify=changed)
    cores = Property("QVariantList", lambda self: [asdict(core) for core in self._cores], notify=coreChoicesChanged)
    coreChoicesRevision = Property(int, lambda self: self._core_choices_revision, notify=coreCatalogueChanged)
    catalogueUpdating = Property(bool, lambda self: False, notify=catalogueStateChanged)
    versionCatalogueRevision = Property(int, lambda self: self._version_catalogue_revision, notify=versionCatalogueChanged)
    buildCoreRevision = Property(int, lambda self: self._build_core_revision, notify=buildCoreChanged)
    coreBrowserModel = Property(QObject, lambda self: self._core_browser_model, constant=True)
    coreBrowserMore = Property(bool, lambda self: False, notify=coreBrowserChanged)
    coreBrowserBusy = Property(bool, lambda self: False, notify=coreBrowserChanged)
    coreBrowserVersions = Property("QVariantList", lambda self: self.minecraftVersions, notify=coreBrowserVersionsChanged)
    installedCoreVersions = Property("QVariantList", lambda self: list(dict.fromkeys(core.minecraft for core in self._cores if core.installed)), notify=installedCoreVersionsChanged)
    downloads = Property("QVariantList", lambda self: [asdict(download) for download in self._downloads], notify=downloadsChanged)
    downloadModel = Property(QObject, lambda self: self._download_model, constant=True)
    modQueue = Property("QVariantList", lambda self: [{**asdict(mod), 'required_by': list(getattr(mod, 'required_by', ()))} for mod in self._mod_queue], notify=changed)
    settings = Property("QVariantMap", lambda self: self._settings.copy(), notify=changed)
    shortcutActions = Property('QVariantList', lambda self: [dict(key=key, default=default, scopes=list(scopes)) for key, default, scopes in SHORTCUT_ACTIONS], constant=True)

    @Slot(int, int, result=str)
    def shortcutFromKey(self, key, modifiers):
        return shortcuts.from_key(key, modifiers)

    @Slot(str, result=str)
    def shortcutLabel(self, sequence):
        return shortcuts.label(sequence)

    @Slot(str, str, result='QVariantMap')
    def checkShortcut(self, action, sequence):
        return shortcuts.check(self._settings, action, sequence)

    @Slot(str, str, result=bool)
    def assignShortcut(self, action, sequence):
        result = self.checkShortcut(action, sequence)
        if not result['valid']:
            return False
        self.command('setting', 'shortcut.' + action, result['sequence'])
        return True

    @Slot(QObject, str, int, result='QVariantMap')
    def findDocument(self, document, text, start):
        if not text or document is None:
            return {}
        cursor = document.find(text, max(0, start))
        if cursor.isNull():
            cursor = document.find(text, 0)
        return {} if cursor.isNull() else dict(start=cursor.selectionStart(), end=cursor.selectionEnd())
    currentPage = Property(str, lambda self: self._page, notify=changed)
    aboutBuildId = Property(str, lambda self: self._about_build, notify=changed)
    selectedId = Property(str, lambda self: self._selected, notify=changed)
    activeAccount = Property(str, lambda self: next((account.name for account in self._accounts if account.id == self._account), "—"), notify=changed)
    activeAccountId = Property(str, lambda self: self._account, notify=changed)
    live = Property(bool, lambda self: False, constant=True)
    minecraftVersions = Property("QVariantList", lambda self: ["1.21.4", "1.21.1", "1.20.1"], notify=minecraftVersionsChanged)
    editorChanged = Signal()
    fileLoaded = Signal(str, str, str)
    fileSaved = Signal(str, str, str)
    buildSaved = Signal(str)
    windowAction = Signal(str)
    editorRevision = Property(int, lambda self: 0, notify=editorChanged)

    @Slot(str, str, str, str, str, str, str, str, str, str, str, str, result=bool)
    @Slot(str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, result=bool)
    @Slot(str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, result=bool)
    def saveBuild(self, key: str, title: str, description: str, background: str, format: str, java: str, minimum: str, maximum: str, args: str, width: str, height: str, fullscreen: str, minecraft: str = "", loader: str = "", loader_version: str = "", title_color: str | None = None) -> bool:
        saved = self.saveDecoration(key, title, description, background, format, title_color)
        if saved:
            if minecraft or loader:
                self._builds = [replace(build, minecraft=minecraft, loader=loader, loader_version="" if loader == "Vanilla" else loader_version) if build.id == key else build for build in self._builds]
                self.changed.emit()
            self.buildSaved.emit(key)
        return saved

    @Slot(str, str, str)
    def importFiles(self, key: str, directory: str, urls: str) -> None:
        self.notice.emit(self.text("notice.preview"))

    @Slot(str, str, str)
    def dropMods(self, key, urls, window_key):
        if self._closing:
            return
        if self.live:
            self._submit_mod_browser(ApplicationCommand('drop_mod', key, urls, (('window_key', window_key),)))
        else:
            self.notice.emit(self.text("notice.preview"))
    revision = Property(int, lambda self: self._revision, notify=localeChanged)
    memoryLimit = Property(int, lambda self: PREVIEW_MEMORY_LIMIT_MB, constant=True)

    @Slot(str, str, result="QVariantList")
    def loaderVersions(self, loader: str, minecraft: str) -> list[str]:
        return [core.version for core in CORES if core.loader == loader and core.minecraft == minecraft] or [""]

    @Slot(str, str)
    def requestVersions(self, loader: str, minecraft: str) -> None:
        pass

    @Slot(str, str, result=bool)
    def catalogueBusy(self, loader: str, minecraft: str) -> bool:
        return False

    @Slot(str, str, result="QVariantList")
    def versionOptions(self, loader: str, minecraft: str) -> list[dict]:
        values = self.minecraftVersions if loader == "Vanilla" else self.loaderVersions(loader, minecraft)
        label = self.text("cores.installed")
        installed = {core.minecraft if loader == "Vanilla" else core.version for core in self._cores if core.installed and core.loader == loader and (loader == "Vanilla" or core.minecraft == minecraft)}
        return [{"value": version, "label": version, "note": label if version in installed else ""} for version in values if version]

    @Slot(str, str, str)
    def browseCores(self, state: str, loader: str, minecraft: str) -> None:
        items = tuple(core for core in self._cores if (not loader or core.loader == loader) and (not minecraft or core.minecraft == minecraft) and (state == "all" or core.installed == (state == "installed")))
        items = tuple(sorted(items, key=lambda core: (core.installed or core.progress >= 0, version_key(core.minecraft), version_key(core.version), core.loader), reverse=True))
        self._core_browser_model.synchronize(items)

    @Slot()
    def updateCatalogue(self) -> None:
        pass

    @Slot()
    def loadMoreCores(self) -> None:
        pass

    @Slot(str, result="QVariantList")
    def editorEntries(self, key: str) -> list[dict]:
        return []

    @Slot(str, result="QVariantList")
    def editorMods(self, key: str) -> list[dict]:
        return []

    @Slot(str, result=QObject)
    def editorModsModel(self, key):
        if key not in self._editor_mod_models:
            model = EditorModsModel(self)
            model.synchronize(self.editorMods(key))
            self._editor_mod_models[key] = model
        return self._editor_mod_models[key]

    def _sync_editor_mod_models(self):
        for key, model in self._editor_mod_models.items():
            model.synchronize(self.editorMods(key))

    @Slot(str, result="QVariantList")
    def editorLogs(self, key: str) -> list[dict]:
        return []

    @Slot(str, str, str, str, str, str, str, str)
    def saveBuildSettings(self, key: str, java_path: str, minimum: str, maximum: str, args: str, width: str, height: str, fullscreen: str) -> None:
        self.buildSaved.emit(key)
    locale = Property(str, lambda self: self._router.request(Request("localization", "current")), notify=localeChanged)
    languages = Property("QVariantList", lambda self: list(self._language_ids if self._language_ids is not None else self._router.request(Request("localization", "available"))), notify=languagesChanged)
    themes = Property("QVariantList", lambda self: list(self._theme_ids if self._theme_ids is not None else self._router.request(Request("themes", "available"))), notify=themesChanged)
    themeIcons = Property('QVariantMap', lambda self: self._router.request(Request('appearance_packs', 'theme_icons')), notify=themesChanged)
    styleCatalogue = Property('QVariantList', lambda self: self._router.request(Request('appearance_packs', 'theme_library')), notify=styleCatalogueChanged)
    styleCatalogueError = Property(str, lambda self: self._router.request(Request('appearance_packs', 'library_error')), notify=styleCatalogueChanged)
    styleCatalogueBusy = Property(bool, lambda self: bool(self._router.request(Request('appearance_packs', 'busy'))), notify=appearanceRefreshChanged)
    styleSelection = Property(str, lambda self: self._style_selection, notify=styleCatalogueChanged)

    @Slot('QVariantList')
    def importThemes(self, urls):
        if self._closing:
            return
        self.command('navigate', 'styles')
        paths = []
        for value in urls:
            url = QUrl(str(value))
            if not url.isLocalFile() or not url.path().lower().endswith('.ugtheme'):
                self.notice.emit(self.text('styles.invalid_file'))
                return
            paths.append(url.toLocalFile())
        if paths:
            self._router.request(Request('appearance_packs', 'import_themes', tuple(paths)))

    @Slot(str)
    def styleInstalled(self, identity):
        self._style_selection = identity
        self.command('navigate', 'styles')
        self.styleCatalogueChanged.emit()
    refreshingLanguages = Property(bool, lambda self: "languages" in self._router.request(Request("appearance_packs", "busy")), notify=appearanceRefreshChanged)
    refreshingThemes = Property(bool, lambda self: "themes" in self._router.request(Request("appearance_packs", "busy")), notify=appearanceRefreshChanged)
    theme = Property(str, lambda self: self._router.request(Request("themes", "current")), notify=themeChanged)
    dirtyEditors = Property("QVariantList", lambda self: sorted(self._dirty_editors), notify=changed)

    def _theme_changed(self, event: Event) -> None:
        self.themeChanged.emit()

    @Slot(str)
    def refreshAppearance(self, kind: str) -> None:
        self._router.request(Request("appearance_packs", "refresh", kind))

    @Slot(object)
    def applyAppearanceCatalogue(self, catalogue: AppearanceCatalogue) -> None:
        if catalogue.kind == "languages":
            self._language_ids = tuple(language.id for language in catalogue.languages)
            for locale in self._language_ids:
                entries = tuple(entry for build in self._builds for entry in (("build." + build.id, build.title), (build.description_key, self.build(build.id).get("description", self.text(build.description_key)))))
                self._router.request(Request("localization", "register", LocaleCatalog(locale, entries)))
            if self.locale not in self._language_ids and self._language_ids:
                fallback = DEFAULT_LOCALE if DEFAULT_LOCALE in self._language_ids else BUILTIN_LOCALE if BUILTIN_LOCALE in self._language_ids else self._language_ids[0]
                self.command("locale", fallback)
            self.languagesChanged.emit()
        else:
            self._theme_ids = tuple(theme.id for theme in catalogue.themes)
            if self.theme not in self._theme_ids and self._theme_ids:
                self.command("theme", DEFAULT_THEME if DEFAULT_THEME in self._theme_ids else self._theme_ids[0])
            self.themesChanged.emit()

    @Slot(str)
    def appearanceRefreshFailed(self, error: str) -> None:
        self.notice.emit(self._router.request(Request("localization", "text", TextQuery("notice.packs_failed", (("details", error),)))))

    @Slot()
    def _sync_build_model(self) -> None:
        cores = {(core.minecraft, core.loader, core.version): core for core in self._cores}
        pending = {item.owner_id for item in self._mod_queue}
        syncing = {item.owner_id for item in self._downloads if item.kind == "mod"}
        states = {}
        for build in self._builds:
            core = cores.get((build.minecraft, build.loader, build.loader_version))
            states[build.id] = BuildCorePreview(core.installed, core.id, core.progress, core.paused, build.id in pending, build.id in syncing, core.stage) if core else BuildCorePreview(False, pending_changes=build.id in pending, syncing=build.id in syncing)
        if states != self._build_core_states:
            self._build_core_states = states
            self._build_core_revision += 1
            self.buildCoreChanged.emit()
        self._build_model.synchronize(tuple(self._builds))

    @Slot(str, result="QVariantMap")
    def buildCoreState(self, key: str) -> dict:
        return asdict(self._build_core_states.get(key, BuildCorePreview(False)))

    def _sync_download_model(self) -> None:
        self._download_model.synchronize(tuple(self._downloads))

    def _locale_changed(self, event: Event) -> None:
        self._revision += 1
        self.localeChanged.emit()

    @Slot(str, result=str)
    def text(self, key: str) -> str:
        return self._router.request(Request("localization", "text", TextQuery(key)))

    @Slot(str, 'QVariantMap', result=str)
    def formatText(self, key, arguments):
        return self._router.request(Request("localization", "text", TextQuery(key, tuple((name, str(value)) for name, value in arguments.items()))))

    @Slot(float, result=str)
    def formatDownloadBytes(self, completed):
        value = QLocale(self.locale).toString(completed / MEBIBYTE_BYTES, 'f', 1)
        return self.formatText('common.mebibytes', {'value': value})

    @Slot(float, result=str)
    def formatDownloadSpeed(self, speed):
        value = QLocale(self.locale).toString(max(0.0, speed) / MEBIBYTE_BYTES, 'f', 1)
        return self.formatText('downloads.speed', {'value': value})

    gameWindowDefaults = Property('QVariantMap', lambda self: dict(width=DEFAULT_GAME_WINDOW_WIDTH, height=DEFAULT_GAME_WINDOW_HEIGHT, minimumWidth=MINIMUM_GAME_WINDOW_WIDTH, minimumHeight=MINIMUM_GAME_WINDOW_HEIGHT, maximumDimension=MAXIMUM_GAME_WINDOW_DIMENSION), constant=True)
    defaultBuildTitleColor = Property(str, lambda self: DEFAULT_BUILD_TITLE_COLOR, constant=True)

    @Slot(str, result=bool)
    def chooseJavaFile(self, value: str) -> bool:
        url = QUrl(value)
        if not url.isLocalFile():
            return False
        self.command("setting", "javaPath", url.toLocalFile())
        return True

    @Slot(str, str, result=str)
    def renderDescription(self, source: str, format: str) -> str:
        return self._router.request(Request("descriptions", "render", DescriptionDocument(source, format)))

    @Slot(str, str, result=str)
    def summarizeDescription(self, source: str, format: str) -> str:
        return self._router.request(Request("descriptions", "summary", DescriptionDocument(source, format)))

    @Slot(str, result="QVariantMap")
    def build(self, key: str) -> dict:
        return next((asdict(build) for build in self._builds if build.id == key), {})

    @Slot(str, result=str)
    def safeId(self, title: str) -> str:
        value = re.sub(r"[^\x20-\x7e]|[<>:\"/\\|?*\s]", "_", title).strip(" .")
        value = re.sub(r"_+", "_", value)
        if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            value = "_" + value
        return value

    @Slot(str, result=str)
    def validateId(self, key: str) -> str:
        if not key or key in (".", "..") or key != self.safeId(key) or len(key) > 96:
            return self.text("validation.id")
        if any(build.id.casefold() == key.casefold() for build in self._builds):
            return self.text("validation.duplicate")
        return ""

    @Slot(str, str)
    @Slot(str, str, str)
    @Slot(str, str, str, str)
    def command(self, action: str, key: str = "", value: str = "", launch_origin: str = "launcher") -> None:
        self._router.request(Request("launcher_preview", "command", PreviewCommand(action, key, value, launch_origin)))

    @Slot(str, str, str, str, str, result=str)
    def createBuild(self, title: str, key: str, minecraft: str, loader: str, loader_version: str) -> str:
        error = self.validateId(key)
        if error or not title.strip():
            return error or self.text("validation.title")
        values = CreateBuildPreview(title.strip(), key, minecraft, loader, loader_version)
        self._router.request(Request("launcher_preview", "create", values))
        return ""

    @Slot(str, str, str, str, result=bool)
    @Slot(str, str, str, str, str, result=bool)
    def saveDecoration(self, key: str, title: str, description: str, background: str, description_format: str = "md", title_color: str | None = None) -> bool:
        return self._router.request(Request("launcher_preview", "decorate", BuildDecorationPreview(key, title, description, background, description_format, title_color)))

    def handle(self, action: str, payload: object) -> object:
        if action == "dirty":
            return tuple(self._dirty_editors)
        if action == "decorate" and isinstance(payload, BuildDecorationPreview):
            if payload.description_format not in ("md", "html"):
                raise ValueError(diagnostic('session.unknown.description.format'))
            if payload.title_color is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", payload.title_color):
                self.notice.emit(self.text("validation.title_color"))
                return False
            if self.build(payload.id).get("running") and self._settings["safeMode"]:
                self.notice.emit(self.text("notice.locked"))
                return False
            if not payload.title.strip():
                self.notice.emit(self.text("validation.title"))
                return False
            description_key = "build.description." + payload.id
            self._builds = [replace(build, title=payload.title.strip(), description_key=description_key, background=payload.background, description_format=payload.description_format, title_color=build.title_color if payload.title_color is None else payload.title_color) if build.id == payload.id else build for build in self._builds]
            for locale in self.languages:
                self._router.request(Request("localization", "register", LocaleCatalog(locale, (("build." + payload.id, payload.title.strip()), (description_key, payload.description)))))
            self.changed.emit()
            return True
        if action == "create" and isinstance(payload, CreateBuildPreview):
            self._builds.append(BuildPreview(payload.id, payload.title, payload.minecraft, payload.loader, payload.loader_version, "demo.new", len(self._builds) % 4))
            for locale in self.languages:
                self._router.request(Request("localization", "register", LocaleCatalog(locale, (("build." + payload.id, payload.title),))))
            self._selected = payload.id
            self.changed.emit()
            self.notice.emit(self.text("notice.created"))
            return None
        if action != "command" or not isinstance(payload, PreviewCommand):
            raise ValueError(diagnostic('session.unknown.preview.request', action))
        key, value = payload.key, payload.value
        if payload.action == "navigate":
            if key not in ("builds", "profile", "cores", "styles", "settings"):
                raise ValueError(key)
            if key == "settings" and self._page != "settings":
                self._page_history.append(self._page)
            elif key != "settings":
                self._page_history.clear()
            self._page = key
        elif payload.action == "back":
            self._page = self._page_history.pop() if self._page_history else "builds"
        elif payload.action == "about_build":
            if not self.build(key):
                raise ValueError(key)
            if self._page != "buildAbout":
                self._page_history.append(self._page)
            self._about_build = key
            self._page = "buildAbout"
        elif payload.action == "select":
            self._selected = key
        elif payload.action == "account":
            self._account = key
        elif payload.action in ("add_account", "rename_account"):
            if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", value):
                self.notice.emit(self.text("validation.account_name"))
                return None
            if any(account.name.casefold() == value.casefold() and (payload.action == "add_account" or account.id != key) for account in self._accounts):
                self.notice.emit(self.text("validation.account_duplicate"))
                return None
            if payload.action == "rename_account":
                self._accounts = [replace(account, name=value, initials=value[:2].upper()) if account.id == key else account for account in self._accounts]
            else:
                identifier = value.lower()
                suffix = 1
                while any(account.id == identifier for account in self._accounts):
                    identifier = value.lower() + ":" + str(suffix)
                    suffix += 1
                self._account = identifier
                self._accounts.append(AccountPreview(self._account, value, value[:2].upper()))
        elif payload.action == "delete_account":
            self._accounts = [account for account in self._accounts if account.id != key]
            if self._account == key:
                self._account = self._accounts[0].id if self._accounts else ""
        elif payload.action == "setting":
            if key not in self._settings:
                raise ValueError(key)
            if key.startswith('shortcut.') and not shortcuts.check(self._settings, key.removeprefix('shortcut.'), value)['valid']:
                self.notice.emit(self.text('validation.setting'))
                return None
            if key in APPLICATION_SETTING_CHOICES and value not in APPLICATION_SETTING_CHOICES[key]:
                self.notice.emit(self.text("validation.setting"))
                return None
            if key in APPLICATION_SETTING_RANGES:
                minimum, maximum = APPLICATION_SETTING_RANGES[key]
                if not value.isdigit() or not minimum <= int(value) <= maximum:
                    self.notice.emit(self.text("validation.setting"))
                    return None
            if key in ("memoryMin", "memoryMax"):
                other_key = "memoryMax" if key == "memoryMin" else "memoryMin"
                number = int(value) if value.isdigit() else 0
                other = int(self._settings[other_key])
                if not MINIMUM_MEMORY_MB <= number <= PREVIEW_MEMORY_LIMIT_MB or (key == "memoryMin" and number > other) or (key == "memoryMax" and number < other):
                    self.notice.emit(self.text("validation.memory"))
                    return None
            if isinstance(self._settings[key], bool):
                self._settings[key] = value == "true"
            else:
                self._settings[key] = value
            self._sync_presentation_settings()
        elif payload.action == "theme":
            self._router.request(Request("themes", "select", key))
            return None
        elif payload.action == "locale":
            self._router.request(Request("localization", "select", key))
        elif payload.action == "edit":
            self._router.request(Request("editor_workspace", "command", EditorCommand("open_build", key)))
        elif payload.action == "editor_dirty":
            if value == "true":
                self._dirty_editors.add(key)
            else:
                self._dirty_editors.discard(key)
        elif payload.action == "editor_save":
            self.editorSaveRequested.emit(key)
        elif payload.action == "editor_discard":
            self.editorDiscardRequested.emit(key)
            if key == "*":
                self._dirty_editors.clear()
            else:
                self._dirty_editors.discard(key)
        elif payload.action == "play":
            self.notice.emit(self.text("notice.no_launch"))
        elif payload.action in ("download", "install_build"):
            if payload.action == "install_build":
                build = next(build for build in self._builds if build.id == key)
                core = next((core for core in self._cores if (core.minecraft, core.loader, core.version) == (build.minecraft, build.loader, build.loader_version)), None)
                if core is None:
                    core = CorePreview(build.loader.lower() + "_" + build.minecraft + "_" + build.loader_version, build.minecraft, build.loader, build.loader_version, False)
                    self._cores.append(core)
                key = core.id
            core = next(core for core in self._cores if core.id == key)
            if not core.installed and not any(download.id == key for download in self._downloads):
                self._downloads.append(DownloadPreview(key, core.loader + " · " + core.minecraft, 0, "core", key))
                self._cores = [replace(item, progress=0, paused=False) if item.id == key else item for item in self._cores]
                self.notice.emit(self.text("notice.preview"))
        elif payload.action == "delete_core":
            core = next(item for item in self._cores if item.id == key)
            in_use = any(build.running and (build.minecraft, build.loader, build.loader_version) == (core.minecraft, core.loader, core.version) for build in self._builds)
            if in_use and self._settings["safeMode"]:
                self.notice.emit(self.text("notice.locked"))
                return None
            if core.installed:
                self._cores = [replace(item, installed=False, progress=-1, paused=False) if item.id == key else item for item in self._cores]
                self.notice.emit(self.text("notice.core_deleted"))
        elif payload.action in ("pause_download", "cancel_download", 'retry_download'):
            download = next((item for item in self._downloads if item.id == key), None)
            if download is None:
                return None
            if payload.action == "cancel_download":
                self._downloads = [item for item in self._downloads if item.id != key]
                self._cores = [replace(item, progress=-1, paused=False) if item.id == download.owner_id and download.kind == "core" else item for item in self._cores]
                self._mod_queue = [replace(item, state="queued") if download.kind == "mod" and "mod:" + item.owner_id + ":" + item.id == key else item for item in self._mod_queue]
            elif payload.action == 'retry_download':
                self._downloads = [replace(item, state='running', error='', progress=0, paused=False) if item.id == key else item for item in self._downloads]
            else:
                self._downloads = [replace(item, paused=not item.paused) if item.id == key else item for item in self._downloads]
                self._cores = [replace(item, paused=not download.paused) if item.id == download.owner_id and download.kind == "core" else item for item in self._cores]
        elif payload.action == "add_mod":
            build = self.build(key)
            if not build or build.get("loader") == "Vanilla":
                return None
            mod = next((item for item in MOD_CATALOG if item.id == (value or "sodium")), None)
            if mod is None:
                raise ValueError(value)
            if not any(item.owner_id == key and item.id == mod.id for item in self._mod_queue):
                self._mod_queue.append(replace(mod, owner_id=key))
        elif payload.action == "remove_queued_mod":
            self._mod_queue = [item for item in self._mod_queue if not (item.owner_id == key and item.id == value and item.state == "queued")]
        elif payload.action in ("sync_mods", "sync_and_play"):
            build = self.build(key)
            if not build or build.get("loader") == "Vanilla" or build.get("running") and self._settings["safeMode"]:
                return None
            for mod in self._mod_queue:
                if mod.owner_id == key and mod.state == "queued":
                    self._downloads.append(DownloadPreview("mod:" + key + ":" + mod.id, mod.title, 0, "mod", key))
            self._mod_queue = [replace(item, state="downloading") if item.owner_id == key and item.state == "queued" else item for item in self._mod_queue]
        elif payload.action == "delete":
            build = next(build for build in self._builds if build.id == key)
            if build.running and self._settings["safeMode"]:
                self.notice.emit(self.text("notice.locked"))
                return None
            self._builds = [build for build in self._builds if build.id != key]
            self._mod_queue = [item for item in self._mod_queue if item.owner_id != key]
            self._downloads = [item for item in self._downloads if item.owner_id != key or item.kind != "mod"]
            self._selected = ""
            self.notice.emit(self.text("notice.deleted"))
        elif payload.action in ("close_client", "kill_client"):
            self._builds = [replace(build, running=False) if build.id == key else build for build in self._builds]
            self.notice.emit(self.text("notice.demo_client"))
        else:
            self.notice.emit(self.text("notice.preview"))
        if not self.live:
            self._core_choices_revision += 1
            self.coreChoicesChanged.emit()
            self.coreCatalogueChanged.emit()
            self.installedCoreVersionsChanged.emit()
        self.changed.emit()
        return None

    def close(self) -> None:
        self._closing = True
        for token in self._subscriptions:
            self._router.request(Request("events", "unsubscribe", token))
        self._subscriptions.clear()

    def stopUpdates(self) -> None:
        pass
