import ctypes
from ctypes import wintypes
from contextlib import contextmanager


class WindowsEvent:
    def __init__(self, name):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateEventW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
        self.kernel.CreateEventW.restype = wintypes.HANDLE
        self.kernel.SetEvent.argtypes = (wintypes.HANDLE,)
        self.kernel.SetEvent.restype = wintypes.BOOL
        self.kernel.ResetEvent.argtypes = (wintypes.HANDLE,)
        self.kernel.ResetEvent.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.name = name
        self.handle = self.kernel.CreateEventW(None, True, False, name)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def set(self):
        if self.handle:
            self.kernel.SetEvent(self.handle)

    def wait(self, milliseconds):
        return self.handle is not None and self.kernel.WaitForSingleObject(self.handle, milliseconds) == 0

    def reset(self):
        if self.handle:
            self.kernel.ResetEvent(self.handle)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def file_version(path):
    library = ctypes.WinDLL('version', use_last_error=True)
    library.GetFileVersionInfoSizeW.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD))
    library.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    library.GetFileVersionInfoW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID)
    library.GetFileVersionInfoW.restype = wintypes.BOOL
    library.VerQueryValueW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.UINT))
    library.VerQueryValueW.restype = wintypes.BOOL
    size = library.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return (0, 0, 0)
    data = ctypes.create_string_buffer(size)
    pointer, length = wintypes.LPVOID(), wintypes.UINT()
    if not library.GetFileVersionInfoW(str(path), 0, size, data) or not library.VerQueryValueW(data, '\\', ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52:
        raise ctypes.WinError(ctypes.get_last_error())
    values = (wintypes.DWORD * 13).from_address(pointer.value)
    if values[0] != 0xFEEF04BD:
        raise ValueError('Invalid Windows executable version metadata')
    return values[2] >> 16, values[2] & 65535, values[3] >> 16


@contextmanager
def background_thread():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentThread.restype = wintypes.HANDLE
    kernel.SetThreadPriority.argtypes = (wintypes.HANDLE, ctypes.c_int)
    kernel.SetThreadPriority.restype = wintypes.BOOL
    handle = kernel.GetCurrentThread()
    entered = kernel.SetThreadPriority(handle, 0x00010000)
    try:
        yield
    finally:
        if entered:
            kernel.SetThreadPriority(handle, 0x00020000)
