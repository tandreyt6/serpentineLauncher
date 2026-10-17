import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtGui import QGuiApplication


class SystemSession(QAbstractNativeEventFilter):
    def __init__(self, lifecycle):
        super().__init__()
        self.lifecycle = lifecycle
        self.pending = False
        self._blocked_windows = set()
        self.user = ctypes.WinDLL('user32', use_last_error=True) if os.name == 'nt' else None
        if self.user is not None:
            self.user.ShutdownBlockReasonCreate.argtypes = (wintypes.HWND, wintypes.LPCWSTR)
            self.user.ShutdownBlockReasonCreate.restype = wintypes.BOOL
            self.user.ShutdownBlockReasonDestroy.argtypes = (wintypes.HWND,)
            self.user.ShutdownBlockReasonDestroy.restype = wintypes.BOOL
            QGuiApplication.instance().installNativeEventFilter(self)
            lifecycle._session.changed.connect(self.refresh)

    def refresh(self):
        if self.user is not None and not self.lifecycle._session.settings.get('delaySystemShutdown', False):
            for window in self._blocked_windows:
                self.user.ShutdownBlockReasonDestroy(window)
            self._blocked_windows.clear()

    def dispatch(self, window, message, confirmed, flags):
        if message == 0x0011:
            delay = self.lifecycle._session.settings.get('delaySystemShutdown', False)
            if delay and not flags & (0x40000000 | 0x00000001):
                if self.user is not None:
                    if self.user.ShutdownBlockReasonCreate(window, self.lifecycle._session.text('settings.shutdown_reason')):
                        self._blocked_windows.add(window)
                return True, 0
            self.pending = True
            self.lifecycle.prepareSystemExit()
            return True, 1
        if message == 0x0016:
            if self.user is not None:
                self.user.ShutdownBlockReasonDestroy(window)
                self._blocked_windows.discard(window)
            if confirmed:
                self.pending = True
                self.lifecycle.prepareSystemExit()
                self.lifecycle.systemExit()
            else:
                self.pending = False
                self.lifecycle.cancelSystemExit()
            return True, 0
        return False, 0

    def nativeEventFilter(self, event_type, pointer):
        if bytes(event_type) not in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            return False, 0
        message = wintypes.MSG.from_address(int(pointer))
        return self.dispatch(message.hWnd, message.message, bool(message.wParam), message.lParam)

    def close(self):
        if self.user is not None:
            QGuiApplication.instance().removeNativeEventFilter(self)
            self.lifecycle._session.changed.disconnect(self.refresh)
            for window in self._blocked_windows:
                self.user.ShutdownBlockReasonDestroy(window)
            self._blocked_windows.clear()
