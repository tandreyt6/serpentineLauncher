from Core.application.diagnostics import diagnostic
from threading import Thread

from PySide6.QtCore import QEvent, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from shiboken6 import isValid

from Core.configuration.settings import APP_ICON, APP_NAME, BACKEND_EVENT_INTERVAL_MS
from Core.game.launch import LaunchManager
from Core.application.runtime import CoreRuntime
from Core.presentation.session import PreviewSession
from Core.presentation.editor.editor_workspace import EditorWorkspace


class LifecycleManager(QObject):
    quitRequested = Signal()
    stopped = Signal()
    shutdownFailed = Signal(str)
    activateRequested = Signal()
    shutdownStarted = Signal()

    def __init__(self, session: PreviewSession, core: CoreRuntime | None = None, editors: EditorWorkspace | None = None) -> None:
        super().__init__()
        self._session = session
        self._core = core
        self._editors = editors
        self._closed = False
        self._exit_after_editors = False
        self._window = None
        self._window_generation = 0
        self._hidden = []
        self._pending_exit = False
        self._stopping = False
        self._tray = None
        self._menu = None
        self._timer = QTimer(self)
        self._timer.setInterval(BACKEND_EVENT_INTERVAL_MS)
        self._timer.timeout.connect(self._attach)
        self._timer.start()
        session.windowAction.connect(self.apply)
        session.changed.connect(self._finish_exit)
        session.localeChanged.connect(self._translate)
        if editors is not None:
            editors.structureChanged.connect(self._editors_changed)
        self.stopped.connect(self._quit)
        self.shutdownFailed.connect(self._shutdown_failed)
        if core is not None:
            QGuiApplication.instance().setQuitOnLastWindowClosed(False)
            self._tray = QSystemTrayIcon(QIcon(str(APP_ICON)), self)
            self._tray.setToolTip(APP_NAME)
            self._menu = QMenu()
            self._show_action = self._menu.addAction("")
            self._show_action.triggered.connect(self.show)
            self._exit_action = self._menu.addAction("")
            self._exit_action.triggered.connect(self.requestExit)
            self._tray.setContextMenu(self._menu)
            self._tray.activated.connect(self._activated)
            self._translate()
            self._tray.show()

    @Slot()
    def _translate(self) -> None:
        if self._menu is not None:
            self._show_action.setText(self._session.text("tray.show"))
            self._exit_action.setText(self._session.text("tray.exit"))

    @Slot()
    def _attach(self) -> None:
        if self._closed or self._stopping:
            return
        if self._window is not None and not isValid(self._window):
            self._window = None
        if self._window is None:
            window = next((window for window in QGuiApplication.allWindows() if isValid(window) and window.objectName() == "launcher.main"), None)
            if window is not None:
                self.rebindMain(window)

    def _main_destroyed(self, generation: int) -> None:
        if not isValid(self) or generation != self._window_generation:
            return
        self._window = None
        self._hidden = [window for window in self._hidden if isValid(window)]
        if not self._closed and not self._stopping:
            self._timer.start()

    def active_clients(self) -> bool:
        return self._core is not None and self._core.app.get("launch", LaunchManager).has_active_clients()

    def rebindMain(self, window) -> None:
        if self._closed:
            return
        if window is None or not isValid(window):
            raise ValueError(diagnostic('lifecycle.main.window.must.be.alive'))
        previous = self._window
        if previous is not None and isValid(previous) and self._core is not None:
            previous.removeEventFilter(self)
        self._hidden = [window if item is previous else item for item in self._hidden if item is previous or isValid(item)]
        self._window = window
        self._window_generation += 1
        generation = self._window_generation
        window.destroyed.connect(lambda: self._main_destroyed(generation))
        if self._core is not None:
            window.installEventFilter(self)
        self._timer.stop()

    def handle(self, action: str, payload: object) -> object:
        if action == "attach":
            self._attach()
            return None
        raise ValueError(action)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._window and event.type() == QEvent.Type.Close and not self._stopping:
            event.ignore()
            if self._session.settings["closeAction"] == "exit" and self._editors is not None and self._editors.windowKeys:
                self._exit_after_editors = True
                self._window.hide()
            elif self.active_clients() or self._session.settings["closeAction"] == "tray":
                self._window.hide()
            else:
                self.requestExit()
            return True
        return super().eventFilter(watched, event)

    @Slot()
    def _editors_changed(self) -> None:
        self._attach()
        if self._exit_after_editors and not self._editors.windowKeys:
            if self._window is not None and not self._window.isVisible() and self._session.settings["closeAction"] == "exit" and not self.active_clients():
                self.requestExit()
            self._exit_after_editors = False

    @Slot(QSystemTrayIcon.ActivationReason)
    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show()

    @Slot()
    def show(self) -> None:
        if self._closed or self._stopping:
            return
        self._attach()
        self._exit_after_editors = False
        for window in self._hidden:
            if isValid(window):
                window.show()
        self._hidden.clear()
        if self._window is not None:
            self._window.showNormal()
            self._window.raise_()
            self._window.requestActivate()
        else:
            self.activateRequested.emit()

    @Slot()
    def showMain(self) -> None:
        if self._closed or self._stopping:
            return
        self._attach()
        self._exit_after_editors = False
        if self._window is not None:
            self._window.showNormal()
            self._window.raise_()
            self._window.requestActivate()
        else:
            self.activateRequested.emit()

    @Slot(str)
    def apply(self, action: str) -> None:
        if self._closed:
            return
        self._attach()
        if action == "show":
            self.show()
        elif action == "hide":
            self._hidden = [window for window in self._hidden if isValid(window)]
            for window in QGuiApplication.allWindows():
                if window.isVisible() and window not in self._hidden:
                    self._hidden.append(window)
            for window in self._hidden:
                window.hide()
        elif action == "minimize" and self._window is not None:
            self._window.showMinimized()

    @Slot()
    def requestExit(self) -> None:
        if self.active_clients():
            self.apply("hide")
            return
        if self._session.dirtyEditors:
            self.show()
            self.quitRequested.emit()
            return
        self._pending_exit = True
        self._finish_exit()

    @Slot(str)
    def resolveExit(self, choice: str) -> None:
        if choice in ("save", "discard"):
            self._pending_exit = True
            self._session.command("editor_save" if choice == "save" else "editor_discard", "*")
            self._finish_exit()

    @Slot()
    def _finish_exit(self) -> None:
        if self._pending_exit and not self._session.dirtyEditors and not self._stopping:
            if self.active_clients():
                self._pending_exit = False
                self.apply("hide")
                return
            self._stopping = True
            self.shutdownStarted.emit()
            self._session.stopUpdates()
            self.apply("hide")
            Thread(target=self._stop_core, name="launcher-shutdown", daemon=True).start()

    def _stop_core(self) -> None:
        try:
            if self._core is not None:
                self._core.close()
            self.stopped.emit()
        except Exception as error:
            self.shutdownFailed.emit(str(error))

    @Slot(str)
    def _shutdown_failed(self, message: str) -> None:
        self._stopping = False
        self._pending_exit = False
        self._session.resumeUpdates()
        self.show()
        self._session.notice.emit(message)

    @Slot()
    def _quit(self) -> None:
        QGuiApplication.quit()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._window_generation += 1
        self._timer.stop()
        self._session.windowAction.disconnect(self.apply)
        self._session.changed.disconnect(self._finish_exit)
        self._session.localeChanged.disconnect(self._translate)
        if self._editors is not None:
            self._editors.structureChanged.disconnect(self._editors_changed)
        if self._window is not None and isValid(self._window) and self._core is not None:
            self._window.removeEventFilter(self)
        self._window = None
        self._hidden.clear()
        if self._tray is not None:
            self._tray.hide()
            self._tray.deleteLater()
            self._tray = None
        if self._menu is not None:
            self._menu.deleteLater()
            self._menu = None
