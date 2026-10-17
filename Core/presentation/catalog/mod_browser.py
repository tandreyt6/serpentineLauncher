from dataclasses import asdict
from uuid import uuid4
import json

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, Qt, Signal, Slot

from Core.application.application_contracts import ApplicationCommand, ModCatalogEntry, ModSearchResult
from Core.configuration.settings import MOD_CATALOGUE_PAGE_SIZE, MOD_SEARCH_QUERY_LENGTH


class ModCatalogModel(QAbstractListModel):
    changed = Signal()
    ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent=None, icons=None):
        super().__init__(parent)
        self._items: list[ModCatalogEntry] = []
        self._icons = icons if icons is not None else {}

    count = Property(int, lambda self: len(self._items), notify=changed)

    def roleNames(self):
        return {self.ROLE: b"key", self.ROLE + 1: b"text", self.ROLE + 2: b"secondary", self.ROLE + 3: b"detail"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        return {self.ROLE: item.id, self.ROLE + 1: item.title, self.ROLE + 2: item.description, self.ROLE + 3: {**asdict(item), 'icon': self._icons.get(item.id, '')}}.get(role)

    def icon_changed(self, project_id):
        row = self.indexOf(project_id)
        if row >= 0:
            self.dataChanged.emit(self.index(row), self.index(row), [self.ROLE + 3])

    def reset(self):
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()
        self.changed.emit()

    def append(self, entries):
        keys = {item.id for item in self._items}
        added = []
        for item in entries:
            if item.id not in keys:
                keys.add(item.id)
                added.append(item)
        if added:
            start = len(self._items)
            self.beginInsertRows(QModelIndex(), start, start + len(added) - 1)
            self._items.extend(added)
            self.endInsertRows()
            self.changed.emit()

    def entry(self, key):
        return next((item for item in self._items if item.id == key), None)

    @Slot(str, result=int)
    def indexOf(self, key):
        return next((index for index, item in enumerate(self._items) if item.id == key), -1)


class ModBrowser(QObject):
    changed = Signal()
    queueChanged = Signal()
    filtersChanged = Signal(str, str)

    def __init__(self, build_id, submit, queue, cancel=None, parent=None, icons=None, defaults=('', ''), content_kind='mod', queue_model=None, *, translate):
        super().__init__(parent)
        self._build_id = build_id
        self._submit = submit
        self._queue = queue
        self._cancel = cancel
        self._model = ModCatalogModel(self, icons)
        self._query = ""
        self._request = ""
        self._task = ""
        self._offset = 0
        self._more = False
        self._busy = False
        self._error = ""
        self._error_key = ""
        self._translate = translate
        self._opened = False
        self._pending: dict[str, str] = {}
        self._category = ''
        self._sort = ''
        self._minecraft, self._loader = defaults
        self._categories = ()
        self._filters_requested = False
        self._filters_task = ''
        self._kind = content_kind
        self._queue_model = queue_model

    model = Property(QObject, lambda self: self._model, constant=True)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    more = Property(bool, lambda self: self._more, notify=changed)
    error = Property(str, lambda self: self._translate(self._error_key) if self._error_key else self._error, notify=changed)
    query = Property(str, lambda self: self._query, notify=changed)
    category = Property(str, lambda self: self._category, notify=changed)
    sort = Property(str, lambda self: self._sort, notify=changed)
    minecraft = Property(str, lambda self: self._minecraft, notify=changed)
    loader = Property(str, lambda self: self._loader, notify=changed)
    categories = Property('QVariantList', lambda self: list(self._categories), notify=changed)
    contentKind = Property(str, lambda self: self._kind, constant=True)
    queueModel = Property(QObject, lambda self: self._queue_model, constant=True)
    queue = Property("QVariantList", lambda self: [{**asdict(item), 'required_by': list(getattr(item, 'required_by', ()))} for item in self._queue() if item.owner_id == self._build_id and getattr(item, 'content_kind', 'mod') == self._kind], notify=queueChanged)

    @Slot()
    def open(self):
        if not self._opened:
            self.search(self._query)

    @Slot(str)
    def search(self, query):
        if self._busy and self._task and self._cancel:
            self._cancel(self._task)
        self._opened = True
        self._query = query.strip()[:MOD_SEARCH_QUERY_LENGTH]
        self._offset = 0
        self._model.reset()
        self._more = False
        self._request_page()

    @Slot()
    def loadMore(self):
        if self._more and not self._busy and not self._error:
            self._request_page()

    @Slot()
    def retry(self):
        if not self._busy:
            self._request_page()

    def _request_page(self):
        self._request = uuid4().hex
        self._busy = True
        self._error = ""
        self._error_key = ""
        self.changed.emit()
        try:
            self._task = self._submit(ApplicationCommand("mod_search", self._build_id, self._query, (("request_id", self._request), ("offset", str(self._offset)), ("limit", str(MOD_CATALOGUE_PAGE_SIZE)), ('category', self._category), ('sort', self._sort), ('minecraft', self._minecraft), ('loader', self._loader), ('content_kind', self._kind))))
        except Exception as error:
            self._busy = False
            self._error = str(error)
            self.changed.emit()

    def accept(self, result: ModSearchResult):
        if result.content_kind != self._kind or result.build_id != self._build_id or result.request_id != self._request or result.offset != self._offset or not self._busy:
            return False
        if result.next_offset < result.offset or result.more and result.next_offset == result.offset:
            self._busy = False
            self._error_key = "editor.error.catalogue_offset"
            self.changed.emit()
            return False
        self._model.append(result.mods)
        self._offset = result.next_offset
        self._more = result.more
        self._busy = False
        self._task = ""
        self.changed.emit()
        icons = [{'id': item.id, 'url': item.icon_url} for item in result.mods if item.icon_url]
        if icons:
            self._submit(ApplicationCommand('mod_icons', self._build_id, json.dumps(icons)))
        return True

    @Slot()
    def requestFilters(self):
        if not self._filters_requested:
            self._filters_requested = True
            self._filters_task = self._submit(ApplicationCommand('mod_filters', self._build_id, fields=(('content_kind', self._kind),)))

    def accept_filters(self, categories):
        self._categories = categories
        self.changed.emit()

    @Slot(str, str, str, str)
    def setFilters(self, category, sort, minecraft, loader):
        if (category, sort, minecraft, loader) != (self._category, self._sort, self._minecraft, self._loader):
            self._category, self._sort, self._minecraft, self._loader = category, sort, minecraft, loader
            self.filtersChanged.emit(minecraft, loader)
            self.search(self._query)

    def task_finished(self, task_id, state, error=""):
        if task_id == self._filters_task and state in ('failed', 'cancelled'):
            self._filters_requested = False
            self._filters_task = ''
        if task_id in self._pending:
            self._pending.pop(task_id)
            self.queueChanged.emit()
        if task_id == self._task and state in ("failed", "cancelled", "completed"):
            self._busy = False
            self._task = ""
            self._error = error
            self._error_key = "" if error else "editor.error.catalogue_cancelled" if state == "cancelled" else "editor.error.catalogue_empty"
            self.changed.emit()

    def invalidate(self):
        if self._opened:
            self.search(self._query)

    @Slot(str, result=bool)
    def isQueued(self, key):
        return key in self._pending.values() or any(item.owner_id == self._build_id and item.id == key for item in self._queue())

    @Slot(str)
    def enqueue(self, key):
        item = self._model.entry(key)
        if item is None or self.isQueued(key):
            return
        task = self._submit(ApplicationCommand("add_mod", self._build_id, item.source, (("id", item.id), ("title", item.title), ('content_kind', self._kind))))
        if task:
            self._pending[task] = key
        self.queueChanged.emit()

    @Slot(str)
    def remove(self, key):
        self._submit(ApplicationCommand("remove_queued_mod", self._build_id, key))

    @Slot()
    def synchronize(self):
        if any(item.owner_id == self._build_id and item.state == "queued" for item in self._queue()):
            self._submit(ApplicationCommand("sync_mods", self._build_id, fields=(('content_kind', self._kind),)))
