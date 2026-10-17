from concurrent.futures import TimeoutError
from threading import Thread

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from Core.application.contracts import Cancelled
from Core.application.tasks import Cancellation, TaskManager
from Core.updates.releases import UpdateManager, Release


class UpdateController(QObject):
    changed = Signal()
    dialogRequested = Signal()
    installRequested = Signal()
    exitPrepared = Signal()
    _finished = Signal(str, object)
    _assigned = Signal(str)

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self._core = core
        self._status = 'idle'
        self._error = ''
        self._release = None
        self._task = ''
        self._progress = 0.0
        self._blockers = []
        self._thread = None
        self._cancel = Cancellation()
        self._closing = False
        self._exit_mode = False
        self._exit_download = False
        self.deferred = False
        self._finished.connect(self._accept)
        self._assigned.connect(self._task_assigned)
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._poll)

    status = Property(str, lambda self: self._status, notify=changed)
    error = Property(str, lambda self: self._error, notify=changed)
    version = Property(str, lambda self: self._release.version if self._release else '', notify=changed)
    progress = Property(float, lambda self: self._progress, notify=changed)
    blockers = Property('QStringList', lambda self: self._blockers, notify=changed)
    busy = Property(bool, lambda self: self._status in ('checking', 'downloading', 'waiting'), notify=changed)
    installable = Property(bool, lambda self: self._core is not None and self._core.app.get('updates', UpdateManager).installable, constant=True)

    def _state(self, status, error=''):
        self._status, self._error = status, error
        self.changed.emit()

    @Slot()
    def check(self):
        if self._closing or self.busy:
            self.dialogRequested.emit()
            return
        self.dialogRequested.emit()
        if self.deferred and self._core is not None and self._core.app.get('updates', UpdateManager).prepared:
            self.installRequested.emit()
        elif self._core is None:
            self._state('preview')
        else:
            self._start('check')

    @Slot()
    def install(self):
        if self._closing or self.busy or not self.installable:
            return
        if self._core.app.get('updates', UpdateManager).prepared:
            self.installRequested.emit()
        elif self._release is not None:
            self._start('download')

    def _start(self, kind):
        self._cancel = Cancellation()
        self._progress = 0.0
        self._state('checking' if kind == 'check' else 'downloading')
        self._thread = Thread(target=self._run, args=(kind, self._cancel), name='launcher-update-' + kind, daemon=True)
        self._thread.start()

    def _run(self, kind, cancellation):
        try:
            manager = self._core.app.get('updates', UpdateManager)
            if kind == 'check':
                result = manager.check(cancellation)
            else:
                tasks = self._core.app.get('tasks', TaskManager)
                task = manager.submit(self._release)
                self._assigned.emit(task)
                while True:
                    try:
                        cancellation.check()
                    except Cancelled:
                        tasks.cancel(task)
                        raise
                    try:
                        result = tasks.wait(task, .1)
                        break
                    except TimeoutError:
                        if any(item.task_id == task and item.state in ('completed', 'cancelled', 'failed') for item in tasks.snapshots()):
                            raise
                        continue
        except Exception as error:
            result = error
        self._finished.emit(kind, result)

    @Slot(str)
    def _task_assigned(self, task):
        if not self._closing:
            self._task = task
            self._timer.start()

    @Slot()
    def _poll(self):
        if self._core is None or self._closing:
            return
        snapshot = next((item for item in self._core.app.get('tasks', TaskManager).snapshots() if item.task_id == self._task), None)
        if snapshot is not None:
            self._progress = snapshot.progress or 0.0
            self.changed.emit()

    @Slot(str, object)
    def _accept(self, kind, result):
        if self._closing:
            return
        self._thread = None
        self._timer.stop()
        if isinstance(result, Exception):
            self._state('error', str(result))
            if self._exit_mode:
                self._core.app.log_error('Launcher update: ' + str(result))
                self._exit_mode = False
                self.exitPrepared.emit()
        elif kind == 'check':
            self._release = result if isinstance(result, Release) else None
            self._state('available' if self._release else 'current' if result is False else 'unpublished')
            if self._exit_mode:
                if self._release and self._exit_download:
                    self._start('download')
                else:
                    self._exit_mode = False
                    self.exitPrepared.emit()
        else:
            self._progress = 1.0
            self._state('ready')
            if self._exit_mode:
                self._exit_mode = False
                self.exitPrepared.emit()
            else:
                self.installRequested.emit()

    def prepare_exit(self, enabled):
        if self._core is None:
            QTimer.singleShot(0, self.exitPrepared.emit)
            return
        self._exit_mode = True
        self._exit_download = enabled and self.installable
        if self._thread is not None:
            return
        if self._core.app.get('updates', UpdateManager).prepared or not self._exit_download:
            self._exit_mode = False
            QTimer.singleShot(0, self.exitPrepared.emit)
        else:
            self._start('check')

    def blocked(self, blockers, error=''):
        self._blockers = blockers
        self._state('blocked', error)
        self.dialogRequested.emit()

    def waiting(self):
        self._state('waiting')

    def defer(self):
        self.deferred = True
        self._state('deferred')

    def close(self):
        self._closing = True
        self._cancel.cancel()
        self._timer.stop()
        if self._thread is not None:
            self._thread.join(15)
