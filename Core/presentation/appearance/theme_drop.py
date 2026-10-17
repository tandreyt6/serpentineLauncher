from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtQuick import QQuickWindow
from PySide6.QtGui import QGuiApplication


class ThemeDropFilter(QObject):
    def __init__(self, install, parent=None):
        super().__init__(parent)
        self.install = install
        self.closed = False
        QGuiApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event):
        if self.closed or not isinstance(watched, QQuickWindow) or event.type() not in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop):
            return False
        urls = event.mimeData().urls()
        if not any(url.path().lower().endswith('.ugtheme') for url in urls):
            return False
        if watched.objectName() != 'launcher.main' or not urls or not all(url.isLocalFile() and url.path().lower().endswith('.ugtheme') for url in urls):
            event.setDropAction(Qt.IgnoreAction)
            event.ignore()
            return True
        event.setDropAction(Qt.CopyAction)
        event.accept()
        if event.type() == QEvent.Drop:
            self.install([url.toString() for url in urls])
        return True

    def close(self):
        self.closed = True
        application = QGuiApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
