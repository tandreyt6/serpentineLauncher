from dataclasses import asdict

from PySide6.QtCore import QAbstractListModel, QModelIndex, Property, Qt, Signal, Slot


class ContentQueueModel(QAbstractListModel):
    changed = Signal()
    detailRole = int(Qt.UserRole) + 1

    def __init__(self, build_id, content_kind, parent=None):
        super().__init__(parent)
        self._build_id, self._kind = build_id, content_kind
        self._items = []
        self._progress = {}

    count = Property(int, lambda self: len(self._items), notify=changed)
    syncing = Property(bool, lambda self: any(item.state == 'downloading' for item in self._items), notify=changed)
    hasDependencies = Property(bool, lambda self: any(item.required_by for item in self._items), notify=changed)

    def roleNames(self):
        return {self.detailRole: b'detail', self.detailRole + 1: b'key', self.detailRole + 2: b'text', self.detailRole + 3: b'modelData'}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=int(Qt.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        key = item.queue_id or item.id
        if role == self.detailRole + 1:
            return key
        if role == self.detailRole + 2:
            return item.title
        if role in (self.detailRole, self.detailRole + 3):
            progress = self._progress.get(key)
            detail = {**asdict(item), 'required_by': list(item.required_by), 'completed_bytes': progress.completed_bytes if progress else 0, 'total_bytes': progress.total_bytes if progress else item.artifact.size if item.artifact else None, 'verified': progress.verified if progress else False, 'task_id': progress.task_id if progress else '', 'progress': min(1, progress.completed_bytes / progress.total_bytes) if progress and progress.total_bytes else 1 if progress and progress.verified else 0}
            return detail if role == self.detailRole else {'key': key, 'text': item.title, 'detail': detail}
        return None

    @Slot(str, result=int)
    def indexOf(self, key):
        return next((row for row, item in enumerate(self._items) if (item.queue_id or item.id) == key), -1)

    def synchronize(self, queue):
        desired = [item for item in queue if item.owner_id == self._build_id and getattr(item, 'content_kind', 'mod') == self._kind]
        keys = {item.queue_id or item.id for item in desired}
        changed = False
        for row in range(len(self._items) - 1, -1, -1):
            key = self._items[row].queue_id or self._items[row].id
            if key not in keys:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._items.pop(row)
                self._progress.pop(key, None)
                self.endRemoveRows()
                changed = True
        for row, item in enumerate(desired):
            key = item.queue_id or item.id
            old = self.indexOf(key)
            if old < 0:
                self.beginInsertRows(QModelIndex(), row, row)
                self._items.insert(row, item)
                self.endInsertRows()
                changed = True
            else:
                if old != row:
                    self.beginMoveRows(QModelIndex(), old, old, QModelIndex(), row)
                    self._items.insert(row, self._items.pop(old))
                    self.endMoveRows()
                if self._items[row] != item:
                    self._items[row] = item
                    if item.state == 'queued':
                        self._progress.pop(key, None)
                    self.dataChanged.emit(self.index(row), self.index(row), [self.detailRole, self.detailRole + 3])
                    changed = True
        if changed:
            self.changed.emit()

    def accept_progress(self, progress):
        row = self.indexOf(progress.key)
        if row >= 0 and self._items[row].state == 'downloading' and self._progress.get(progress.key) != progress:
            self._progress[progress.key] = progress
            self.dataChanged.emit(self.index(row), self.index(row), [self.detailRole, self.detailRole + 3])
