from dataclasses import asdict, fields
from uuid import uuid4
import json

from PySide6.QtCore import QObject, Property, Signal, Slot
from Core.application.application_contracts import ApplicationCommand
from Core.configuration.settings import MODRINTH_PROJECT_URL


class ModProject(QObject):
    changed = Signal()
    queueChanged = Signal()
    versionsChanged = Signal()

    def __init__(self, build_id, project_id, submit, queue, icons, parent=None, defaults=('', ''), content_kind='mod', *, translate):
        super().__init__(parent)
        self.build_id, self.project_id = build_id, project_id
        self._submit, self._queue, self._icons = submit, queue, icons
        self._data = {}
        self._versions = ()
        self._version_rows = None
        self._busy = False
        self._error = ''
        self._error_key = ''
        self._translate = translate
        self._request = ''
        self._task = ''
        self._pending = ''
        self._filter = ''
        self._channel = ''
        self._minecraft, self._loader = defaults
        self.content_kind = content_kind

    data = Property('QVariantMap', lambda self: {**self._data, 'icon': self._icons.get(self.project_id, '')}, notify=changed)
    def _visible_versions(self):
        if self._version_rows is None:
            self._version_rows = [{**asdict(item), 'minecraft': list(item.minecraft), 'loaders': list(item.loaders)} for item in self._versions if (not self._channel or item.channel == self._channel) and (not self._minecraft or self._minecraft in item.minecraft) and (not self._loader or self._loader in item.loaders) and self._filter in (item.number + ' ' + item.name).casefold()]
        return self._version_rows

    def _invalidate_versions(self):
        self._version_rows = None
        self.versionsChanged.emit()

    versions = Property('QVariantList', _visible_versions, notify=versionsChanged)
    minecraft = Property(str, lambda self: self._minecraft, notify=changed)
    loader = Property(str, lambda self: self._loader, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    error = Property(str, lambda self: self._translate(self._error_key) if self._error_key else self._error, notify=changed)
    queue = Property('QVariantMap', lambda self: next((asdict(item) for item in self._queue() if item.owner_id == self.build_id and item.id == self.project_id), {}), notify=queueChanged)
    queuedVersions = Property('QVariantList', lambda self: [item.version_id for item in self._queue() if item.owner_id == self.build_id and item.id == self.project_id], notify=queueChanged)
    pending = Property(bool, lambda self: bool(self._pending), notify=queueChanged)

    @Slot()
    def open(self):
        if not self._busy and not self._data:
            self.reload()

    @Slot()
    def reload(self):
        self._request = uuid4().hex
        self._busy, self._error = True, ''
        self._error_key = ''
        self._task = self._submit(ApplicationCommand('mod_project', self.build_id, self.project_id, (('request_id', self._request), ('content_kind', self.content_kind))))
        self.changed.emit()

    def accept(self, result):
        if result.content_kind != self.content_kind or result.build_id != self.build_id or result.request_id != self._request:
            return
        self.project_id = result.project_id
        self._data = {field.name: getattr(result, field.name) for field in fields(result) if field.name != 'versions'}
        self._versions = result.versions
        self._invalidate_versions()
        self._busy, self._task = False, ''
        self.changed.emit()
        if result.icon_url:
            self._submit(ApplicationCommand('mod_icons', self.build_id, json.dumps([{'id': result.project_id, 'url': result.icon_url}])))

    def task_finished(self, task, state, error=''):
        if task == self._pending:
            self._pending = ''
            self.queueChanged.emit()
        if task == self._task:
            self._busy, self._task = False, ''
            self._error = error
            self._error_key = '' if error else 'editor.error.project_failed'
            self.changed.emit()

    @Slot(str, str, str, str)
    def filterVersions(self, query, channel, minecraft, loader):
        selected = query.strip().casefold(), channel, minecraft.strip(), loader
        if selected == (self._filter, self._channel, self._minecraft, self._loader):
            return
        self._filter, self._channel, self._minecraft, self._loader = selected
        self._invalidate_versions()
        self.changed.emit()

    @Slot(str, str)
    def setCatalogFilters(self, minecraft, loader):
        if (self._minecraft, self._loader) != (minecraft, loader):
            self._minecraft, self._loader = minecraft, loader
            self._invalidate_versions()
            self.changed.emit()

    @Slot(str)
    @Slot(str, str)
    def enqueue(self, version, window_key=''):
        if self._pending or not any(item.id == version for item in self._versions):
            return
        self._pending = self._submit(ApplicationCommand('add_mod', self.build_id, MODRINTH_PROJECT_URL + '/' + self.content_kind + '/' + self.project_id, (('id', self.project_id), ('title', self._data['title']), ('version_id', version), ('window_key', window_key), ('content_kind', self.content_kind))))
        self.queueChanged.emit()

    def invalidate(self):
        if self._data or self._busy:
            self._data = {}
            self.reload()
