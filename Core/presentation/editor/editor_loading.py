
from PySide6.QtCore import QObject, QTimer
from PySide6.QtQml import QQmlIncubator
from PySide6.QtQuick import QQuickItem
from shiboken6 import isValid


class PageIncubator(QQmlIncubator):
    def __init__(self, load, properties):
        super().__init__(QQmlIncubator.IncubationMode.Asynchronous)
        self.load = load
        self.setInitialProperties(properties)

    def setInitialState(self, item):

        QObject.setParent(item, self.load.owner._engine)
        if isinstance(item, QQuickItem):
            item.setVisible(False)
            if isValid(self.load.host):
                item.setWidth(self.load.host.width())
                item.setHeight(self.load.host.height())

    def statusChanged(self, status):
        if status in (QQmlIncubator.Status.Ready, QQmlIncubator.Status.Error):
            QTimer.singleShot(0, self.load, self.load.finish)


class PageLoad(QObject):
    def __init__(self, owner, key, host, component, properties):
        super().__init__(owner)
        self.owner, self.key, self.host, self.component = owner, key, host, component
        self.active = True
        self.waiting_item = None
        self.incubator = PageIncubator(self, properties)
        host.destroyed.connect(self.cancel)
        component.statusChanged.connect(self.component_changed)

    def start(self):
        self.component_changed(self.component.status())

    def component_changed(self, status):
        if not self.active:
            return
        if self.component.isError():
            self.owner._page_finished(self, None, self.component.errors())
        elif self.component.isReady() and self.incubator.isNull():
            self.component.create(self.incubator)

    def finish(self):
        if self.active:
            self.owner._page_finished(self, self.incubator.object(), self.incubator.errors())

    def await_ui(self, item):
        if self.waiting_item is None:
            self.waiting_item = item
            item.uiReadyChanged.connect(self.finish)

    def cancel(self):
        if not self.active:
            return
        self.active = False
        if self.waiting_item is not None and isValid(self.waiting_item):
            self.waiting_item.uiReadyChanged.disconnect(self.finish)
        if isValid(self.host):
            self.host.destroyed.disconnect(self.cancel)
        if isValid(self.component):
            self.component.statusChanged.disconnect(self.component_changed)
        item = self.incubator.object()
        self.incubator.clear()
        if item is not None and isValid(item) and item.parent() is self.owner._engine:
            item.deleteLater()
        if self.owner._pending_pages.get(self.key) is self:
            self.owner._pending_pages.pop(self.key)
        self.deleteLater()
