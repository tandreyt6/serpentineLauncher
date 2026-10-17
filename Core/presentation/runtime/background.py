from threading import Event

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from Core.configuration.settings import BACKEND_EVENT_INTERVAL_MS
from Core.cli.instance import InstanceDriver
from Core.application.application_contracts import ApplicationSnapshot, BackendResult
from Core.application.contracts import CoreEvent
from Core.game.launch import LaunchManager
from Core.application.router import EventManager
from Core.application.runtime import CoreRuntime
from Core.application.tasks import TaskManager
from Core.application.application_store import ApplicationStore
from Core.presentation.runtime.startup import create_loading_application
from Core.presentation.runtime.lifecycle import LifecycleManager
from Core.presentation.appearance.localization import language_messages


class BackgroundSession(QObject):
    changed = Signal()
    localeChanged = Signal()
    notice = Signal(str)
    windowAction = Signal(str)

    def __init__(self, core: CoreRuntime) -> None:
        super().__init__()
        self._core = core
        self.settings = dict(core.app.get("application_store", ApplicationStore).snapshot().settings)
        self._messages = language_messages(self.settings['locale'])
        self.dirtyEditors = []
        self._timer = QTimer(self)
        self._timer.setInterval(BACKEND_EVENT_INTERVAL_MS)
        self._timer.timeout.connect(self._drain)
        self._timer.start()

    @Slot()
    def _drain(self) -> None:
        self._core.app.get("events", EventManager).drain()

    def update(self, snapshot: ApplicationSnapshot) -> None:
        old_locale = self.settings.get("locale")
        self.settings = dict(snapshot.settings)
        self.changed.emit()
        if old_locale != self.settings.get("locale"):
            self._messages = language_messages(self.settings['locale'])
            self.localeChanged.emit()

    def text(self, key: str) -> str:
        return self._messages[key]

    def stopUpdates(self) -> None:
        self._timer.stop()

    def resumeUpdates(self) -> None:
        self._timer.start()


class BackgroundController(QObject):
    def __init__(self, core: CoreRuntime, activation: Event) -> None:
        super().__init__()
        self._core = core
        self._activation = activation
        self._session = BackgroundSession(core)
        self._lifecycle = LifecycleManager(self._session, core)
        self._lifecycle.activateRequested.connect(self._activate)
        self._application = None
        self._timer = QTimer(self)
        self._timer.setInterval(BACKEND_EVENT_INTERVAL_MS)
        self._timer.timeout.connect(self._check)
        self._timer.start()
        events = core.app.get("events", EventManager)
        events.subscribe("application", self._event)
        events.subscribe("backend", self._event)

    def _event(self, event: CoreEvent) -> None:
        if isinstance(event.payload, ApplicationSnapshot):
            self._session.update(event.payload)
        elif isinstance(event.payload, BackendResult) and event.payload.action == "activate":
            self._activation.set()

    @Slot()
    def _activate(self) -> None:
        self._activation.set()

    @Slot()
    def _check(self) -> None:
        if self._activation.is_set():
            self._timer.stop()
            self._session.stopUpdates()
            self._lifecycle.close()
            events = self._core.app.get("events", EventManager)
            events.unsubscribe("application", self._event)
            events.unsubscribe("backend", self._event)
            self._application, startup = create_loading_application(core=self._core, activation=self._activation)
            self._activation.clear()
            return
        active = self._core.app.get("launch", LaunchManager).has_active_clients()
        busy = any(task.state in ("queued", "running", "retrying", "paused", "cancelling") for task in self._core.app.get("tasks", TaskManager).snapshots())
        if not active and not busy and self._session.settings.get("closeAction") == "exit":
            self._timer.stop()
            self._lifecycle.requestExit()

    def close(self) -> None:
        self._timer.stop()
        self._session.stopUpdates()
        self._lifecycle.close()
        events = self._core.app.get("events", EventManager)
        events.unsubscribe("application", self._event)
        events.unsubscribe("backend", self._event)
        if self._application is not None:
            self._application.close()


def main(core: CoreRuntime, activation: Event) -> int:
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    controller = BackgroundController(core, activation)
    try:
        return application.exec()
    finally:
        controller.close()
