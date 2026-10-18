import ctypes
from ctypes import wintypes
from hashlib import sha256
import os
from pathlib import Path
import sys


def executable_path():
    if os.name != 'nt':
        return Path(sys.executable).resolve()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleFileNameW.argtypes = (wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD)
    kernel.GetModuleFileNameW.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel.GetModuleFileNameW(None, buffer, len(buffer))
    if not length or length >= len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    return Path(buffer.value).resolve()


def installation_lock_name(root):
    path = str(Path(root).resolve()).rstrip('\\/').lower()
    return 'Local\\SerpentineInstall-' + sha256(path.encode('utf-8')).hexdigest()


def updating(root=None):
    if os.name != 'nt':
        return False
    if root is None:
        from Core.updates.package import EXECUTABLE
        executable = executable_path()
        if executable.name.casefold() != EXECUTABLE.casefold():
            return False
        root = executable.parent
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.OpenMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenMutexW(0x00100001, False, installation_lock_name(root))
    if not handle:
        return ctypes.get_last_error() == 5
    try:
        state = kernel.WaitForSingleObject(handle, 0)
        if state in (0, 0x80):
            kernel.ReleaseMutex(handle)
            return False
        return True
    finally:
        kernel.CloseHandle(handle)
