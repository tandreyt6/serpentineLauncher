
from PySide6.QtCore import QAbstractListModel, QModelIndex, Property, Qt, Signal


class EditorModsModel(QAbstractListModel):
    changed = Signal()
    rowRole = int(Qt.UserRole) + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    count = Property(int, lambda self: len(self._items), notify=changed)

    def roleNames(self):
        return {self.rowRole: b'modelData'}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=int(Qt.DisplayRole)):
        if role == self.rowRole and index.isValid() and 0 <= index.row() < len(self._items):
            return self._items[index.row()]
        return None

    @staticmethod
    def _key(item):
        return item['path'].casefold()

    def synchronize(self, items):
        desired = [dict(item) for item in items]
        keys = {self._key(item) for item in desired}
        old_keys = {self._key(item) for item in self._items}
        added = {self._key(item): item for item in desired if self._key(item) not in old_keys}

        for row, old in enumerate(self._items):
            key = self._key(old)
            if key not in keys:
                counterpart = key.removesuffix('.disabled') if key.endswith('.disabled') else key + '.disabled'
                if counterpart in added:
                    self._items[row] = added.pop(counterpart)
                    self.dataChanged.emit(self.index(row), self.index(row), [self.rowRole])
        count_changed = False
        for row in range(len(self._items) - 1, -1, -1):
            if self._key(self._items[row]) not in keys:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._items.pop(row)
                self.endRemoveRows()
                count_changed = True
        for row, item in enumerate(desired):
            key = self._key(item)
            existing = next((i for i in range(row, len(self._items)) if self._key(self._items[i]) == key), -1)
            if existing < 0:
                self.beginInsertRows(QModelIndex(), row, row)
                self._items.insert(row, item)
                self.endInsertRows()
                count_changed = True
            else:
                if existing != row:
                    self.beginMoveRows(QModelIndex(), existing, existing, QModelIndex(), row)
                    self._items.insert(row, self._items.pop(existing))
                    self.endMoveRows()
                if self._items[row] != item:
                    self._items[row] = item
                    self.dataChanged.emit(self.index(row), self.index(row), [self.rowRole])
        if count_changed:
            self.changed.emit()
