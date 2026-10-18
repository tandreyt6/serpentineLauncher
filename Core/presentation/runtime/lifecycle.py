from Core.application.diagnostics import diagnostic
from threading import Thread
from time import monotonic

from PySide6.QtCore import QEvent, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from shiboken6 import isValid

from Core.configuration.settings import APP_ICON, APP_NAME, BACKEND_EVENT_INTERVAL_MS
from Core.game.launch import LaunchManager
from Core.application.runtime import CoreRuntime
from Core.presentation.session import PreviewSession
from Core.presentation.editor.editor_workspace import EditorWorkspace
from Core.presentation.runtime.updates import UpdateController
from Core.application.tasks import TaskManager
from Core.updates.releases import UpdateManager
from Core.presentation.runtime.system_session import SystemSession
import os


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
        self._update_requested = False
        self._update_restart = False
        self._update_exit_ready = False
        self._update_exit_preparing = False
        self._system_exit = False
        self._prefetch_scheduled = False
        self._background_restart = False
        self._background_update_pending = False
        self._resume_window = None
        self.updates = UpdateController(core, self)
        self.updates.installRequested.connect(self.requestUpdate)
        self.updates.exitPrepared.connect(self._update_prepared)
        self.updates.backgroundReady.connect(self._background_ready)
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(100)
        self._update_timer.timeout.connect(self._wait_update)
        self._tray = None
        self._menu = None
        self._timer = QTimer(self)
        self._timer.setInterval(BACKEND_EVENT_INTERVAL_MS)
        self._timer.timeout.connect(self._attach)
        self._timer.start()
        session.windowAction.connect(self.apply)
        session.changed.connect(self._finish_exit)
        session.changed.connect(self._try_background_update)
        session.changed.connect(self._sync_system_policy)
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
        self._system_session = SystemSession(self) if core is not None else None
        self._prefetch_timer = QTimer(self)
        self._prefetch_timer.setSingleShot(True)
        self._prefetch_timer.timeout.connect(self._prefetch_update)
        self._sync_system_policy()

    def _sync_system_policy(self):
        if self._core is not None:
            self._core.app.get('updates', UpdateManager).configure_policy(
                self._session.settings.get('delaySystemShutdown', False), self._session.text('settings.shutdown_reason'))

    def _prefetch_update(self):
        if self._stopping or self._system_exit:
            return
        startup = self._session._router._departments.get('launcher_startup')
        if startup is not None and startup.phase != 'shown':
            self._prefetch_timer.start(200)
            return
        from Core.updates import resume
        if resume.state is not None:
            if self._session.settings['silentUpdates']:
                self.updates.prefetch()
        else:
            self.updates.startup(self._session.settings['startupUpdatePrompt'], self._session.settings['silentUpdates'])

    def _background_ready(self):
        self._background_update_pending = True
        self._try_background_update()

    def _try_background_update(self):
        if not self._background_update_pending or self._system_exit or self._stopping or not self._session.settings.get('silentUpdates', True):
            return
        if any(key != 'updates.blocker.clients' for key in self._update_blockers()) or self._editors is not None and self._editors.windowKeys:
            return
        if any(client.state in ('starting', 'closing') for client in self._core.app.get('launch', LaunchManager).snapshots()):
            return
        self._attach()
        if self._window is None:
            return
        from Core.presentation.runtime.quiet_resume import capture
        self._resume_window = capture(self._window, self._session.currentPage)
        self._background_restart = True
        self._update_requested = True
        self._update_restart = True
        self._update_exit_ready = True
        self._pending_exit = True
        self._finish_exit()

    def prepareSystemExit(self):
        self._system_exit = True
        self._prefetch_timer.stop()
        self._update_timer.stop()
        self.updates.interrupt()
        if self._core is not None:
            self._core.app.get('updates', UpdateManager).abort()

    def cancelSystemExit(self):
        self._system_exit = False
        self._pending_exit = False
        self._update_exit_preparing = False
        if self._core is not None:
            self._core.app.get('updates', UpdateManager).resume()

    def systemExit(self):
        os._exit(0)

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
        if not self._prefetch_scheduled:
            self._prefetch_scheduled = True
            self._prefetch_timer.start(5000)

    def handle(self, action: str, payload: object) -> object:
        if action == "attach":
            self._attach()
            return None
        raise ValueError(action)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._window and event.type() == QEvent.Type.Close and not self._stopping:
            event.ignore()
            updater = self._core.app.get('updates', UpdateManager) if self._core is not None else None
            if updater is not None and updater.prepared is not None and (self._session.settings.get('silentUpdates', True) or self.updates.deferred):
                self._update_restart = False
                self._request_update() if self._update_blockers() else self.requestExit()
            elif self._session.settings["closeAction"] == "exit" and self._editors is not None and self._editors.windowKeys:
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
        if self._stopping or self._system_exit:
            return
        if self.active_clients():
            self.apply("hide")
            return
        if self._session.dirtyEditors:
            self.show()
            self.quitRequested.emit()
            return
        if not self._pending_exit:
            self._update_exit_ready = False
        self._pending_exit = True
        self._finish_exit()

    def _update_blockers(self):
        blockers = []
        if self.active_clients():
            blockers.append('updates.blocker.clients')
        if self._session.dirtyEditors:
            blockers.append('updates.blocker.editors')
        if self._core is not None:
            updater = self._core.app.get('updates', UpdateManager)
            if any(task.task_id != updater.download_task and task.state in ('queued', 'running', 'retrying', 'paused', 'cancelling') for task in self._core.app.get('tasks', TaskManager).snapshots()):
                blockers.append('updates.blocker.tasks')
        return blockers

    @Slot()
    def requestUpdate(self):
        self._update_restart = True
        self._request_update()

    def _request_update(self):
        if self._stopping or self._system_exit or self._core is None:
            return
        if self._core.app.get('updates', UpdateManager).prepared is None:
            return
        blockers = self._update_blockers()
        if blockers:
            self.updates.blocked(blockers)
            return
        self._update_requested = True
        self._pending_exit = True
        self._update_exit_ready = True
        self._finish_exit()

    def _cancel_tasks(self):
        if self._core is not None:
            tasks = self._core.app.get('tasks', TaskManager)
            own = self._core.app.get('updates', UpdateManager).download_task
            for task in tasks.snapshots():
                if task.task_id != own and task.state in ('queued', 'running', 'retrying', 'paused'):
                    tasks.cancel(task.task_id)

    @Slot(str)
    def resolveUpdate(self, choice):
        if choice == 'later':
            self._update_timer.stop()
            self._pending_exit = False
            self._update_requested = False
            self._update_restart = False
            self.updates.defer()
        elif choice == 'continue' and self._core is not None:
            self._cancel_tasks()
            launch = self._core.app.get('launch', LaunchManager)
            for client in launch.snapshots():
                if client.state in ('starting', 'running'):
                    launch.request_close(client.build_id)
            if self._session.dirtyEditors:
                self._session.command('editor_save', '*')
            self._update_deadline = monotonic() + 60
            self.updates.waiting()
            self._update_timer.start()

    @Slot()
    def _wait_update(self):
        blockers = self._update_blockers()
        if not blockers:
            self._update_timer.stop()
            self._request_update()
        elif monotonic() >= self._update_deadline:
            self._update_timer.stop()
            self.updates.blocked(blockers, self._session.text('updates.close_timeout'))

    @Slot()
    def _update_prepared(self):
        self._update_exit_preparing = False
        self._update_exit_ready = True
        if self._pending_exit and self._session.dirtyEditors:
            self._pending_exit = False
            if self._update_requested:
                self.updates.blocked(self._update_blockers())
            else:
                self.quitRequested.emit()
        self._finish_exit()

    @Slot(str)
    def resolveExit(self, choice: str) -> None:
        if choice in ("save", "discard"):
            self._pending_exit = True
            self._session.command("editor_save" if choice == "save" else "editor_discard", "*")
            self._finish_exit()

    @Slot()
    def _finish_exit(self) -> None:
        if self._system_exit:
            return
        if self._pending_exit and not self._session.dirtyEditors and not self._stopping:
            if self.active_clients() and not self._background_restart:
                self._pending_exit = False
                if self._update_requested:
                    self.updates.blocked(self._update_blockers())
                else:
                    self.apply("hide")
                return
            if not self._update_exit_ready:
                if not self._update_exit_preparing:
                    self._update_exit_preparing = True
                    self._cancel_tasks()
                    self.updates.prepare_exit(bool(self._session.settings.get('silentUpdates', True) or self.updates.deferred or self._update_requested))
                return
            self._stopping = True
            self.shutdownStarted.emit()
            self._session.stopUpdates()
            self.apply("hide")
            Thread(target=self._stop_core, name="launcher-shutdown", daemon=True).start()

    def _stop_core(self) -> None:
        plan = None
        committed = False
        detached = False
        try:
            if self._core is not None:
                updater = self._core.app.get('updates', UpdateManager)
                if not self._system_exit and updater.prepared is not None and (self._session.settings.get('silentUpdates', True) or self.updates.deferred or self._update_requested):
                    try:
                        plan = updater.arm(self._update_restart,
                            show_progress=self._update_requested and self._update_restart and not self._background_restart,
                            locale=self._session.settings['locale'])
                        if self._background_restart:
                            launch = self._core.app.get('launch', LaunchManager)
                            clients = launch.export_clients(updater._process.pid)
                            updater.handoff(plan, clients, self._resume_window)
                            updater.commit(plan, True)
                            committed = True
                            launch.detach_clients()
                            detached = True
                    except Exception as error:
                        if self._update_requested:
                            raise
                        self._core.app.log_error('Launcher update: ' + str(error))
                self._core.close()
                if plan is not None and not committed and not self._system_exit:
                    updater.commit(plan, self._update_restart)
            self.stopped.emit()
        except Exception as error:
            if committed and detached:
                try:
                    self._core.app.log_error('Launcher shutdown after client handoff: ' + str(error))
                finally:
                    os._exit(0)
                return
            if plan is not None:
                if self._background_restart:
                    try:
                        updater.release_handoff(plan)
                    except Exception as release_error:
                        self._core.app.log_error('Launcher client handoff cancellation: ' + str(release_error))
                try:
                    updater.disarm(plan)
                except OSError as cancellation_error:
                    self._core.app.log_error('Launcher update cancellation: ' + str(cancellation_error))
            self.shutdownFailed.emit(str(error))

    @Slot(str)
    def _shutdown_failed(self, message: str) -> None:
        background = self._background_restart
        self._stopping = False
        self._pending_exit = False
        self._update_requested = False
        self._update_restart = False
        self._background_restart = False
        self._background_update_pending = False
        self._session.resumeUpdates()
        if background:
            from Core.presentation.runtime.quiet_resume import restore
            if self._window is not None and self._resume_window is not None:
                restore(self._window, self._resume_window)
            self.updates._state('error', message)
            self._core.app.log_error('Background launcher update: ' + message)
        else:
            self.show()
            self._session.notice.emit(message)

    @Slot()
    def _quit(self) -> None:
        QGuiApplication.quit()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._system_session is not None:
            self._system_session.close()
        self._window_generation += 1
        self._timer.stop()
        self._update_timer.stop()
        self._prefetch_timer.stop()
        self.updates.close()
        self._session.windowAction.disconnect(self.apply)
        self._session.changed.disconnect(self._finish_exit)
        self._session.changed.disconnect(self._try_background_update)
        self._session.changed.disconnect(self._sync_system_policy)
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
