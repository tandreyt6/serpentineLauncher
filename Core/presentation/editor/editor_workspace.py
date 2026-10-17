from Core.application.diagnostics import diagnostic
from dataclasses import asdict

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PySide6.QtQuick import QQuickItem, QQuickWindow
from shiboken6 import isValid

from Core.configuration.settings import UI_DIRECTORY
from Core.presentation.contracts import EditorCommand, EditorSaveState, EditorTab, PreviewCommand
from Core.presentation.editor.editor_catalog import CONFIGS, LOGS, config_entries
from Core.presentation.editor.editor_loading import PageLoad
from universal_gui.app_manager import AppManager
from universal_gui.contracts import Event, LocaleCatalog, Request, TextQuery
from universal_gui.qt.workspace import TabAction, TabDefinition, TabGroup, TabInsert
from universal_gui.qt.window_contracts import FloatingWindowSpec, WindowOwnerContext, WindowCloseDecision, WindowLifecycle
from universal_gui.qt.document_buffer import DocumentBuffer
from universal_gui.ui_contracts import DocumentSnapshot, SaveIntent
from universal_gui.services.events import Subscription


class EditorWorkspace(QObject):
    changed = Signal()
    structureChanged = Signal()
    loadingChanged = Signal()
    confirmationRequested = Signal(str, str)

    def __init__(self, router: AppManager, engine: QQmlEngine) -> None:
        super().__init__()
        self._router = router
        self._engine = engine
        self._windows: dict[str, QQuickWindow] = {}
        self._documents: dict[str, DocumentBuffer] = {}
        self._save_revisions: dict[str, list[tuple[int, str]]] = {}
        self._close_requests: set[str] = set()
        self._tabs: dict[str, EditorTab] = {}
        self._pages: dict[str, QQuickItem] = {}
        self._pending_pages: dict[str, PageLoad] = {}
        self._failed_pages: set[str] = set()
        self._save_states: dict[str, bool] = {}
        self._components: dict[str, QQmlComponent] = {}
        self._buffers: dict[tuple[str, str], str] = {}
        self._subscriptions: dict[str, str] = {}
        self._counter = 0
        self._revision = 0
        self._structure_revision = 0
        self._signature: tuple[tuple[str, tuple[str, ...]], ...] = ()
        self._closed = False
        self._session = None
        self._pending_files: dict[tuple[str, str], str] = {}
        self._pending_close: set[str] = set()
        self._watch("workspace.drag.changed")
        self._watch("locale.changed")
        self._watch("windows.lifecycle")
        self._watch("runtime.closing")

    revision = Property(int, lambda self: self._revision, notify=changed)
    structureRevision = Property(int, lambda self: self._structure_revision, notify=structureChanged)
    windowKeys = Property("QVariantList", lambda self: list(self._windows), notify=changed)
    loadingKeys = Property("QVariantList", lambda self: [key for key in self._tabs if key not in self._pages and key not in self._failed_pages], notify=loadingChanged)

    def attach(self, session: QObject) -> None:
        self._session = session
        self.structureChanged.connect(self._update_editor_watches)
        session.fileLoaded.connect(self._file_loaded)
        session.fileSaved.connect(self._file_saved)
        session.changed.connect(self._finish_closing)
        session.modTitleReady.connect(self._mod_title_ready)

    def _update_editor_watches(self):
        if self._session.live:
            self._session.watchEditorBuilds(list({tab.build_id for tab in self._tabs.values()}))

    def _mod_title_ready(self, build_id, project_id, title):
        tag = 'editor.mod.' + build_id + '.' + project_id
        for locale in self._router.request(Request('localization', 'available')):
            self._router.request(Request('localization', 'register', LocaleCatalog(locale, ((tag, title),))))
        self._refresh()

    @Slot(str, str, str)
    def _file_loaded(self, build: str, path: str, text: str) -> None:
        target = self._pending_files.pop((build, path), None)
        if target is not None:
            self._buffers[(build, path)] = text
            self._open(EditorTab(build + ":" + path, build, "file", path), target)

    @Slot(str, str, str)
    def _file_saved(self, build: str, path: str, text: str) -> None:
        self._buffers[(build, path)] = text
        key = build + ":" + path
        document = self._documents.get(key)
        revisions = self._save_revisions.get(key, [])
        match = next((revision for revision, snapshot in revisions if snapshot == text), None)
        if document is not None and match is not None:
            document.acknowledge(match)
            self._save_revisions[key] = [(revision, snapshot) for revision, snapshot in revisions if revision > match]

    @Slot(object)
    def _save_document(self, intent: SaveIntent) -> None:
        if not isinstance(intent, SaveIntent):
            raise TypeError(diagnostic('editor_workspace.expected.saveintent'))
        pending = self._save_revisions.setdefault(intent.document, [])
        pending.append((intent.revision, intent.text))
        del pending[:-16]
        self.saveFile(intent.document, intent.text)

    @Slot(str, result=str)
    def savedText(self, key: str) -> str:
        tab = self._tabs[key]
        return self._buffers.get((tab.build_id, tab.path), "")

    @Slot()
    def _finish_closing(self) -> None:
        dirty = self._router.request(Request("launcher_preview", "dirty", None))
        ready = tuple(key for key in self._pending_close if key not in dirty)
        self._pending_close.difference_update(ready)
        for key in ready:
            if key in self._tabs:
                self._remove_tab(key)
        if ready:
            self._refresh()

    def _workspace(self, action: str, payload: object = None) -> object:
        return self._router.request(Request("workspace", action, payload))

    def _watch(self, topic: str) -> None:
        if topic not in self._subscriptions:
            self._subscriptions[topic] = self._router.request(Request("events", "subscribe", Subscription(topic, self._on_event)))

    def _on_event(self, event: Event) -> None:
        if event.topic == "runtime.closing":
            for load in tuple(self._pending_pages.values()):
                load.cancel()
            return
        if event.topic == "windows.lifecycle" and isinstance(event.payload, WindowLifecycle):
            if event.payload.phase == "request-close":
                group = event.payload.group_key
                self._close_requests.add(group)
                if self.dirty(group):
                    self._show_confirmation(group)
                else:
                    self.command("close_window", group, "")
                return
            if event.payload.phase == "final-closed":
                self._close_requests.discard(event.payload.group_key)
        self._refresh()

    @Slot(str, result="QVariantList")
    def tabs(self, group: str) -> list[dict]:
        definitions, _ = self._workspace("snapshot", group)
        return [asdict(self._tabs[tab.key]) for tab in definitions if tab.key in self._tabs]

    @Slot(str, result=str)
    def selected(self, group: str) -> str:
        return self._workspace("snapshot", group)[1]

    @Slot(str, result=QObject)
    def currentPage(self, group):
        page = self._pages.get(self.selected(group))
        return page if page is not None and isValid(page) else None

    @Slot()
    def saveAll(self):
        dirty = self._router.request(Request('launcher_preview', 'dirty', None))
        for key in tuple(dirty):
            if self._save_states.get(key, False):
                self._router.request(Request('launcher_preview', 'command', PreviewCommand('editor_save', key)))

    @Slot(str, result=bool)
    def dirty(self, group: str) -> bool:
        dirty = self._router.request(Request("launcher_preview", "dirty", None))
        return any(tab["key"] in dirty for tab in self.tabs(group))

    @Slot(str, result=bool)
    def buildDirty(self, build_id: str) -> bool:
        dirty = self._router.request(Request("launcher_preview", "dirty", None))
        return any(tab.key in dirty for tab in self._tabs.values() if tab.build_id == build_id)

    @Slot(str, result=bool)
    def canSaveBuild(self, build_id: str) -> bool:
        dirty = self._router.request(Request("launcher_preview", "dirty", None))
        return any(self._save_states.get(tab.key, False) for tab in self._tabs.values() if tab.build_id == build_id and tab.key in dirty)

    @Slot(str, bool)
    def reportSaveState(self, key: str, available: bool) -> None:
        self._router.request(Request("editor_workspace", "save_state", EditorSaveState(key, available)))

    @Slot()
    def _save_state_changed(self) -> None:
        self._revision += 1
        self.changed.emit()

    @Slot(str, result="QVariantList")
    def configs(self, directory: str) -> list[dict]:
        return config_entries(directory)

    @Slot(result="QVariantList")
    def logs(self) -> list[dict]:
        from Core.application.log_format import format_log
        return [dict(asdict(log), formatted_text=format_log(log.text)) for log in LOGS]

    @Slot(str, str, str)
    def command(self, action: str, key: str, target: str) -> None:
        self._router.request(Request("editor_workspace", "command", EditorCommand(action, key, target)))

    @Slot(str, str, str)
    def openFile(self, build_id: str, path: str, group: str) -> None:
        self._router.request(Request("editor_workspace", "command", EditorCommand("open_file", build_id, group, path)))

    @Slot(str, str, str)
    def openMod(self, build_id, project_id, group):
        self._router.request(Request('editor_workspace', 'command', EditorCommand('open_mod', build_id, group, project_id)))

    @Slot(str, str, str)
    def openContentCatalog(self, build_id, content_kind, group):
        self._router.request(Request('editor_workspace', 'command', EditorCommand('open_mod_catalog', build_id, group, content_kind=content_kind)))

    @Slot(str, str, str, str)
    def openContent(self, build_id, project_id, content_kind, group):
        self._router.request(Request('editor_workspace', 'command', EditorCommand('open_mod', build_id, group, project_id, content_kind=content_kind)))

    @Slot(str, str)
    def saveFile(self, key: str, text: str) -> None:
        self._router.request(Request("editor_workspace", "command", EditorCommand("save_file", key, value=text)))

    @Slot(str, str, int)
    def moveTab(self, key: str, target: str, index: int) -> None:
        self._workspace("move", TabAction(self._group_of(key), key, target, index))
        self._refresh()
        self._focus(target)

    def handle(self, action: str, payload: object) -> object:
        if action == "save_state" and isinstance(payload, EditorSaveState):
            if payload.key in self._tabs and self._save_states.get(payload.key) != payload.available:
                self._save_states[payload.key] = payload.available
                self._save_state_changed()
            return None
        if action != "command" or not isinstance(payload, EditorCommand):
            raise ValueError(diagnostic('editor_workspace.invalid.editor.request', action))
        command = payload
        if command.action == "open_build":
            return self._open(EditorTab(command.key, command.key, "build"), command.target)
        if command.action == "open_mod_catalog":
            if self._session is not None:
                build = self._session.build(command.key)
                if not build or command.content_kind == 'mod' and build.get("loader") == "Vanilla":
                    return None
            return self._open(EditorTab(command.key + ":" + command.content_kind + "-catalog", command.key, "catalog", content_kind=command.content_kind), command.target)
        if command.action == 'open_mod':
            if self._session is not None and not self._session.build(command.key):
                return None
            if self._session is not None:
                self._session.applyCatalogFilters(command.key, command.value, command.content_kind)
            return self._open(EditorTab(command.key + ':' + command.content_kind + ':' + command.value, command.key, 'mod', command.value, command.content_kind), command.target)
        if command.action == 'return_mod_catalog':
            tab = self._tabs.get(command.key)
            if tab is not None and tab.kind == 'mod':
                group = self._group_of(tab.key)
                self._remove_tab(tab.key)
                self._open(EditorTab(tab.build_id + ':' + tab.content_kind + '-catalog', tab.build_id, 'catalog', content_kind=tab.content_kind), group)
            return None
        if command.action == "open_file":
            if self._session is not None and self._session.live:
                existing = command.key + ":" + command.value
                if existing in self._tabs:
                    return self.handle("command", EditorCommand("select", existing))
                self._pending_files[(command.key, command.value)] = command.target
                self._router.request(Request("launcher_preview", "read_file", command))
                return None
            if not any(entry.path == command.value for entry in CONFIGS):
                raise ValueError(command.value)
            return self._open(EditorTab(command.key + ":" + command.value, command.key, "file", command.value), command.target)
        if command.action == "save_file":
            tab = self._tabs[command.key]
            if self._session is not None and self._session.live:
                return self._router.request(Request("launcher_preview", "save_file", EditorCommand("save_file", tab.build_id, command.value, tab.path)))
            self._file_saved(tab.build_id, tab.path, command.value)
            return None
        if command.action in ("save_build", "discard_build"):
            dirty = self._router.request(Request("launcher_preview", "dirty", None))
            keys = tuple(tab.key for tab in self._tabs.values() if tab.build_id == command.key and tab.key in dirty)
            operation = "editor_save" if command.action == "save_build" else "editor_discard"
            for key in keys:
                self._router.request(Request("launcher_preview", "command", PreviewCommand(operation, key)))
            return None
        if command.action in ("save_tab", "discard_tab"):
            self._pending_close.add(command.key)
            self._router.request(Request("launcher_preview", "command", PreviewCommand("editor_save" if command.action == "save_tab" else "editor_discard", command.key)))
            self._finish_closing()
            return None
        if command.action == "select":
            group = self._group_of(command.key)
            self._workspace("select", TabAction(group, command.key))
            self._refresh()
            self._focus(group)
            return None
        if command.action == "detach":
            self._workspace("detach", TabAction(self._group_of(command.key), command.key))
            self._refresh()
            return self._group_of(command.key)
        if command.action == "close_tab":
            self._remove_tab(command.key)
            self._refresh()
            return None
        if command.action in ("close_window", "save_window", "discard_window"):
            keys = tuple(tab["key"] for tab in self.tabs(command.key))
            if command.action != "close_window":
                self._pending_close.update(keys)
                operation = "editor_save" if command.action == "save_window" else "editor_discard"
                for key in keys:
                    self._router.request(Request("launcher_preview", "command", PreviewCommand(operation, key)))
                self._finish_closing()
                return not self.dirty(command.key)
            if self.dirty(command.key):
                return False
            for key in keys:
                self._remove_tab(key)
            self._refresh()
            return True
        raise ValueError(command.action)

    def _component(self, source: str) -> QQmlComponent:
        component = self._components.get(source)
        if component is None:
            component = QQmlComponent(self._engine, self._sceneUrl(source), QQmlComponent.CompilationMode.Asynchronous)
            self._components[source] = component
        return component

    def _page_finished(self, load, item, errors):
        if not load.active:
            return
        host = load.host
        if not errors and item is not None and not isinstance(item, QQuickItem):
            error = QQmlError()
            error.setUrl(load.component.url())
            error.setDescription("Editor page must create a QQuickItem")
            errors = [error]
        if not self._closed and load.key in self._tabs and isValid(host) and isinstance(item, QQuickItem):
            waiting = item.metaObject().indexOfProperty("uiReady") >= 0 and not item.property("uiReady")
            if waiting:
                load.await_ui(item)
                item.setOpacity(0)
                item.setEnabled(False)
            item.setProperty("workspaceKey", self._group_of(load.key))
            QObject.setParent(item, host)
            item.setParentItem(host)
            QQmlProperty(item, "anchors.fill").write(host)
            item.setVisible(True)
            if waiting:
                return
            if load.waiting_item is not None:
                item.setOpacity(1)
                item.setEnabled(True)
            self._pages[load.key] = item
            self.loadingChanged.emit()
            if host.metaObject().indexOfProperty("loading") >= 0:
                host.setProperty("loading", False)
        elif errors and not self._closed:
            self._failed_pages.add(load.key)
            self.loadingChanged.emit()
            self._engine.warnings.emit(errors)
            if isValid(host) and host.metaObject().indexOfProperty("loading") >= 0:
                host.setProperty("loading", False)
            if self._session is not None:
                self._session.notice.emit("\n".join(error.toString() for error in errors))
        load.cancel()

    def _sceneUrl(self, source: str) -> QUrl:
        return QUrl(self._router.request(Request("theme_scenes", "view_url", source)))

    def clearViewCache(self) -> None:
        if self._windows:
            raise RuntimeError(diagnostic('editor_workspace.cannot.replace.editor.views.while.windows'))
        for component in self._components.values():
            component.deleteLater()
        self._components.clear()

    @Slot(QObject, str)
    def mountPage(self, host: QObject, key: str) -> None:
        if self._closed or key not in self._tabs:
            return
        if not isinstance(host, QQuickItem):
            raise TypeError(diagnostic('editor_workspace.editor.page.host.must.be.a'))
        tab = self._tabs[key]
        self._failed_pages.discard(key)
        if key in self._pending_pages:
            self._pending_pages[key].cancel()
        properties = {"buildId": tab.build_id, "workspaceKey": self._group_of(key)}
        source = "editor/EditorBuild.qml"
        if tab.kind == "catalog":
            source = "editor/ModCatalog.qml"
            properties.update(contentKind=tab.content_kind)
        if tab.kind == 'mod':
            source = 'editor/ModProject.qml'
            properties.update(projectId=tab.path, tabKey=tab.key, contentKind=tab.content_kind)
        if tab.kind == "file":
            text = self._buffers.get((tab.build_id, tab.path), next((entry.text for entry in CONFIGS if entry.path == tab.path), ""))
            self._buffers.setdefault((tab.build_id, tab.path), text)
            document = self._documents.get(key)
            if document is None:
                document = DocumentBuffer(self)
                document.load_snapshot(DocumentSnapshot(key, text))
                document.saveRequested.connect(self._save_document)
                self._documents[key] = document
            properties.update(tabKey=key, filePath=tab.path, documentBuffer=document)
            source = "editor/TextEditor.qml"
        load = PageLoad(self, key, host, self._component(source), properties)
        self._pending_pages[key] = load
        load.start()
        self.loadingChanged.emit()

    def _open(self, tab: EditorTab, target: str) -> str:
        existing = self._group_of(tab.key) if tab.key in self._tabs else ""
        if existing:
            self._workspace("select", TabAction(existing, tab.key))
            self._refresh()
            self._focus(existing)
            return existing
        same_scope = tuple(key for key in self._windows if (group_state := self._workspace("group", key)) is not None and group_state.scope_key == tab.build_id)
        group = target if target in same_scope else next(reversed(same_scope), "")
        self._tabs[tab.key] = tab
        self.loadingChanged.emit()
        title_tag = "build." + tab.build_id
        if tab.kind == "catalog":
            title_tag = "editor." + tab.content_kind + "_catalog"
        if tab.kind == 'mod':
            title_tag = 'editor.mod.' + tab.build_id + '.' + tab.path
            for locale in self._router.request(Request('localization', 'available')):
                self._router.request(Request('localization', 'register', LocaleCatalog(locale, ((title_tag, tab.path),))))
        if tab.kind == "file":
            title_tag = "editor.file." + tab.key
            for locale in self._router.request(Request("localization", "available")):
                self._router.request(Request("localization", "register", LocaleCatalog(locale, ((title_tag, tab.path.split("/")[-1]),))))
        source = self._sceneUrl("editor/EditorPage.qml")
        definition = TabDefinition(tab.key, title_tag, source.toString())
        if group:
            self._workspace("add", TabInsert(group, definition))
        else:
            self._counter += 1
            home = "editor-home-" + str(self._counter)
            body = self._components.get("editor/EditorWindow.qml")
            if body is None:
                body = QQmlComponent(self._engine, self._sceneUrl("editor/EditorWindow.qml"))
                if body.isError():
                    raise ValueError("\n".join(error.toString() for error in body.errors()))
                self._components["editor/EditorWindow.qml"] = body
            options = FloatingWindowSpec(close_policy="request", empty_policy="close", owner_context=WindowOwnerContext(tab.build_id, tab.build_id), body_content=body)
            self._workspace("register", TabGroup(home, (definition,), True, scope_key=tab.build_id, floating=options))
            self._workspace("detach", TabAction(home, tab.key))
            self._workspace("unregister", home)
            group = self._group_of(tab.key)
        self._refresh()
        self._focus(group)
        return group

    def _group_of(self, key: str) -> str:
        return self._workspace("find_group", key)

    def _remove_tab(self, key: str) -> None:
        if key in self._pending_pages:
            self._pending_pages[key].cancel()
        group = self._group_of(key)
        tab = self._tabs.get(key)
        self._router.request(Request("launcher_preview", "command", PreviewCommand("editor_dirty", key, "false")))
        self._tabs.pop(key, None)
        self._failed_pages.discard(key)
        self.loadingChanged.emit()
        self._pages.pop(key, None)
        self._save_states.pop(key, None)
        document = self._documents.pop(key, None)
        self._save_revisions.pop(key, None)
        self._workspace("remove", TabAction(group, key))
        if tab is not None and tab.kind == 'mod' and self._session is not None:
            self._session.releaseModProject(tab.build_id, tab.path, tab.content_kind)
        if document is not None:
            document.deleteLater()

    @Slot(str)
    def requestCloseTab(self, key: str) -> None:
        group = self._group_of(key)
        dirty = self._router.request(Request("launcher_preview", "dirty", None))
        if key in dirty:
            self._show_confirmation(group, key)
        else:
            self.command("close_tab", key, "")

    def _show_confirmation(self, group: str, key: str = "") -> None:
        self.confirmationRequested.emit(group, key)

    @Slot(str)
    def cancelClose(self, group: str) -> None:
        if group in self._close_requests:
            self._close_requests.discard(group)
            self._workspace("respond_close", WindowCloseDecision(group, False))

    def _refresh(self) -> None:
        if self._closed:
            return
        groups = tuple(dict.fromkeys(self._group_of(key) for key in self._tabs))
        if self._workspace("dragging"):
            groups += tuple(group for group in self._windows if group not in groups and self._workspace("group", group) is not None)
        for group in groups:
            self._watch("tabs.changed." + group)
            if group not in self._windows:
                window = self._router.request(Request("windows", "floating_window", group))
                if window is None:
                    continue
                self._windows[group] = window
                window.setObjectName("launcher.editor." + group)
            selected = self.selected(group)
            if selected in self._tabs:
                tab = self._tabs[selected]
                title_tag = "editor.file." + tab.key if tab.kind == "file" else "editor.mod." + tab.build_id + '.' + tab.path if tab.kind == 'mod' else "editor." + tab.content_kind + "_catalog" if tab.kind == "catalog" else "build." + tab.build_id
                title = self._router.request(Request("localization", "text", TextQuery(title_tag)))
                caption = self._router.request(Request("localization", "text", TextQuery("app.editor")))
                self._windows[group].setTitle(title + " · " + caption)
            for tab in self.tabs(group):
                page = self._pages.get(tab["key"])
                if page is not None and isValid(page):
                    page.setProperty("workspaceKey", group)
        for group in tuple(self._windows):
            if group not in groups:
                self._windows.pop(group)
                topic = "tabs.changed." + group
                self._router.request(Request("events", "unsubscribe", self._subscriptions.pop(topic)))
        signature = tuple((group, tuple(tab["key"] for tab in self.tabs(group))) for group in groups)
        if signature != self._signature:
            self._signature = signature
            self._structure_revision += 1
            self.structureChanged.emit()
        self._revision += 1
        self.changed.emit()

    def _focus(self, group: str) -> None:
        window = self._windows.get(group)
        if window is not None and isValid(window):
            window.show()
            window.raise_()
            window.requestActivate()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for load in tuple(self._pending_pages.values()):
            load.cancel()
        if self._session is not None:
            self._session.fileLoaded.disconnect(self._file_loaded)
            self._session.fileSaved.disconnect(self._file_saved)
            self._session.changed.disconnect(self._finish_closing)
        for token in self._subscriptions.values():
            self._router.request(Request("events", "unsubscribe", token))
        self._subscriptions.clear()
        self._tabs.clear()
        for component in self._components.values():
            component.deleteLater()
        self._windows.clear()
        for document in self._documents.values():
            document.deleteLater()
        self._documents.clear()
        self._save_revisions.clear()
        self._pages.clear()
        self._save_states.clear()
        self._components.clear()
        self._pending_files.clear()
        self._pending_close.clear()
        self._close_requests.clear()
        self._buffers.clear()
