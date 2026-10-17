from dataclasses import asdict

from PySide6.QtCore import QAbstractListModel, QModelIndex, Property, Qt, Signal, Slot

from Core.presentation.contracts import BuildFilter, BuildPreview, CorePreview, DownloadPreview


class CoreListModel(QAbstractListModel):
    changed = Signal()
    projectionChanged = Signal()
    role = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[CorePreview] = []
        self._revision = 0

    count = Property(int, lambda self: len(self._items), notify=changed)
    dataRevision = Property(int, lambda self: self._revision, notify=projectionChanged)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return {self.role: b"modelData", self.role + 1: b"key", self.role + 2: b"text", self.role + 3: b"progress"}

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.role:
            return asdict(item)
        return {self.role + 1: item.id, self.role + 2: item.loader, self.role + 3: item.progress}.get(role)

    @Slot(str, result="QVariantMap")
    def entry(self, key: str) -> dict:
        return next((asdict(item) for item in self._items if item.id == key), {})

    def synchronize(self, items: tuple[CorePreview, ...]) -> None:
        if tuple(self._items) == items:
            return
        old_ids = tuple(item.id for item in self._items)
        new_ids = tuple(item.id for item in items)
        if old_ids == new_ids[:len(old_ids)] and len(items) >= len(self._items):
            for row, item in enumerate(items[:len(self._items)]):
                if item != self._items[row]:
                    self._items[row] = item
                    self.dataChanged.emit(self.index(row), self.index(row), list(self.roleNames()))
            if len(items) > len(self._items):
                start = len(self._items)
                self.beginInsertRows(QModelIndex(), start, len(items) - 1)
                self._items.extend(items[start:])
                self.endInsertRows()
                self.changed.emit()
        else:
            self.beginResetModel()
            self._items = list(items)
            self.endResetModel()
            self.changed.emit()
        self._revision += 1
        self.projectionChanged.emit()


class DownloadListModel(QAbstractListModel):
    changed = Signal()
    role = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[DownloadPreview] = []

    count = Property(int, lambda self: len(self._items), notify=changed)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return {self.role: b"modelData"}

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object:
        return asdict(self._items[index.row()]) if role == self.role and index.isValid() and 0 <= index.row() < len(self._items) else None

    def synchronize(self, items: tuple[DownloadPreview, ...]) -> None:
        if tuple(self._items) == items:
            return
        if tuple(item.id for item in self._items) == tuple(item.id for item in items):
            for row, item in enumerate(items):
                if self._items[row] != item:
                    self._items[row] = item
                    self.dataChanged.emit(self.index(row), self.index(row), [self.role])
            return
        structural = False
        keys = {item.id for item in items}
        for row in range(len(self._items) - 1, -1, -1):
            if self._items[row].id not in keys:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._items.pop(row)
                self.endRemoveRows()
                structural = True
        for row, item in enumerate(items):
            existing = next((index for index, current in enumerate(self._items) if current.id == item.id), None)
            if existing is None:
                self.beginInsertRows(QModelIndex(), row, row)
                self._items.insert(row, item)
                self.endInsertRows()
                structural = True
            else:
                if existing != row:
                    self.beginMoveRows(QModelIndex(), existing, existing, QModelIndex(), row)
                    self._items.insert(row, self._items.pop(existing))
                    self.endMoveRows()
                    structural = True
                if self._items[row] != item:
                    self._items[row] = item
                    self.dataChanged.emit(self.index(row), self.index(row), [self.role])
        if structural:
            self.changed.emit()


class BuildListModel(QAbstractListModel):
    changed = Signal()
    role = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, builds: tuple[BuildPreview, ...], parent=None) -> None:
        super().__init__(parent)
        self._builds = builds
        self._items = list(builds)
        self._filter = BuildFilter()

    count = Property(int, lambda self: len(self._items), notify=changed)
    activeFilters = Property(int, lambda self: sum(bool(value) for value in (self._filter.name, self._filter.id, self._filter.minecraft, self._filter.loader, self._filter.loader_version)) + int(self._filter.state != "all"), notify=changed)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return {self.role: b"modelData", self.role + 1: b"key", self.role + 2: b"text"}

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object:
        if index.isValid() and 0 <= index.row() < len(self._items):
            item = self._items[index.row()]
            if role == self.role:
                return asdict(item)
            return {self.role + 1: item.id, self.role + 2: item.title}.get(role)
        return None

    @Slot(str, str, str, str, str, str)
    def setFilters(self, name: str, key: str, minecraft: str, loader: str, loader_version: str, state: str) -> None:
        if state not in ("all", "running", "idle"):
            raise ValueError(state)
        self._filter = BuildFilter(name.strip(), key.strip(), minecraft, loader, loader_version, state)
        self.synchronize(self._builds)
        self.changed.emit()

    def _matches(self, build: BuildPreview) -> bool:
        criteria = self._filter
        return criteria.name.casefold() in build.title.casefold() and criteria.id.casefold() in build.id.casefold() and (not criteria.minecraft or criteria.minecraft == build.minecraft) and (not criteria.loader or criteria.loader == build.loader) and (not criteria.loader_version or criteria.loader_version == build.loader_version) and (criteria.state == "all" or build.running == (criteria.state == "running"))

    def synchronize(self, builds: tuple[BuildPreview, ...]) -> None:
        self._builds = builds
        desired = [build for build in builds if self._matches(build)]
        if desired == self._items:
            return
        if tuple(item.id for item in self._items) == tuple(item.id for item in desired):
            for row, item in enumerate(desired):
                if self._items[row] != item:
                    self._items[row] = item
                    self.dataChanged.emit(self.index(row), self.index(row), list(self.roleNames()))
            return
        keys = {build.id for build in desired}
        for row in range(len(self._items) - 1, -1, -1):
            if self._items[row].id not in keys:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._items.pop(row)
                self.endRemoveRows()
        for row, build in enumerate(desired):
            existing = next((index for index, item in enumerate(self._items) if item.id == build.id), None)
            if existing is None:
                self.beginInsertRows(QModelIndex(), row, row)
                self._items.insert(row, build)
                self.endInsertRows()
            else:
                if existing != row:
                    self.beginMoveRows(QModelIndex(), existing, existing, QModelIndex(), row)
                    self._items.insert(row, self._items.pop(existing))
                    self.endMoveRows()
                if self._items[row] != build:
                    self._items[row] = build
                    self.dataChanged.emit(self.index(row), self.index(row), list(self.roleNames()))
        self.changed.emit()
