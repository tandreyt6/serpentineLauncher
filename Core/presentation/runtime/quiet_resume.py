import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickWindow

from Core.updates import resume


def native():
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user.GetWindow.restype = wintypes.HWND
    user.IsWindow.argtypes = (wintypes.HWND,)
    user.IsWindow.restype = wintypes.BOOL
    user.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
    user.SetWindowPos.restype = wintypes.BOOL
    user.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user.ShowWindow.restype = wintypes.BOOL
    user.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
    user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    return user


def capture(window, page):
    rect = window.geometry()
    return dict(x=rect.x(), y=rect.y(), width=rect.width(), height=rect.height(),
        visible=window.isVisible(), minimized=window.visibility() == QQuickWindow.Visibility.Minimized,
        maximized=window.visibility() == QQuickWindow.Visibility.Maximized, flags=int(window.flags()),
        above=int(native().GetWindow(int(window.winId()), 3) or 0), page=page)


def open_quiet(app):
    manager = app.runtime.router._departments['windows']
    component = QQmlComponent(app.runtime.engine, QUrl.fromLocalFile(manager._definitions['main']))
    saved = resume.state['window']
    window = component.createWithInitialProperties(dict(visible=False, opacity=0.0,
        flags=Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus))
    if not isinstance(window, QQuickWindow):
        raise ValueError('\n'.join(error.toString() for error in component.errors()))
    QObject.setParent(window, app.runtime.engine)
    component.setParent(window)
    manager._track_window('main', window)
    window.setGeometry(int(saved['x']), int(saved['y']), int(saved['width']), int(saved['height']))
    window.show()
    return window


def restore(window, saved=None):
    saved = saved if saved is not None else resume.state['window']
    window.hide()
    flags = Qt.WindowType(int(saved['flags']))
    window.setFlags(flags | Qt.WindowType.WindowDoesNotAcceptFocus)
    window.setGeometry(int(saved['x']), int(saved['y']), int(saved['width']), int(saved['height']))
    window.setOpacity(1.0)
    if saved['visible']:
        if saved['minimized']:
            window.showMinimized()
        elif saved['maximized']:
            window.showMaximized()
        else:
            window.show()
    window.setFlags(flags)
    if saved['visible']:
        user = native()
        handle = int(window.winId())
        if saved['minimized']:
            user.ShowWindow(handle, 7)
        else:
            above = int(saved.get('above', 0))
            if not above or not user.IsWindow(above) or user.GetWindowLongPtrW(above, -20) & 8:
                above = 1
            user.SetWindowPos(handle, above, 0, 0, 0, 0, 0x0010 | 0x0200 | 0x0040 | 0x0001 | 0x0002)
