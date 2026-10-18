import ctypes
from ctypes import wintypes
import os
import sys


def initialize() -> None:
    if os.name != "nt":
        return
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetConsoleProcessList.argtypes = (ctypes.POINTER(wintypes.DWORD), wintypes.DWORD)
    kernel.GetConsoleProcessList.restype = wintypes.DWORD
    processes = (wintypes.DWORD * 1)()
    if not kernel.GetConsoleProcessList(processes, len(processes)):
        return
    kernel.GetFileType.argtypes = (wintypes.HANDLE,)
    kernel.GetFileType.restype = wintypes.DWORD
    kernel.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.GetConsoleMode.restype = wintypes.BOOL
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        try:
            handle = msvcrt.get_osfhandle(stream.fileno())
        except (AttributeError, OSError, ValueError):
            handle = None
        mode = wintypes.DWORD()
        if handle is not None and (kernel.GetFileType(handle) in (1, 3) or kernel.GetConsoleMode(handle, ctypes.byref(mode))):
            continue
        setattr(sys, name, open("CONOUT$", "w", encoding="utf-8", buffering=1))
