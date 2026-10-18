import ctypes
from ctypes import wintypes
from hashlib import sha256
import os
from pathlib import Path
import sys


def installation_lock_name(root):
    path = str(Path(root).resolve()).rstrip('\\/').lower()
    return 'Local\\SerpentineInstall-' + sha256(path.encode('utf-8')).hexdigest()


def updating(root=None):
    if os.name != 'nt':
        return False
    if root is None:
        from Core.updates.package import EXECUTABLE
        if Path(sys.executable).name != EXECUTABLE:
            return False
        root = Path(sys.executable).resolve().parent
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
