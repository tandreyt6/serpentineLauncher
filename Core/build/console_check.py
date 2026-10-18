import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import struct
import sys


class Coordinate(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short)]


class Rectangle(ctypes.Structure):
    _fields_ = [("left", ctypes.c_short), ("top", ctypes.c_short), ("right", ctypes.c_short), ("bottom", ctypes.c_short)]


class ConsoleInfo(ctypes.Structure):
    _fields_ = [("size", Coordinate), ("cursor", Coordinate), ("attributes", wintypes.WORD), ("window", Rectangle), ("maximum", Coordinate)]


def probe(executable, output):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.argtypes = (wintypes.DWORD,)
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.GetConsoleScreenBufferInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(ConsoleInfo))
    kernel.GetConsoleScreenBufferInfo.restype = wintypes.BOOL
    kernel.ReadConsoleOutputCharacterW.argtypes = (wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, Coordinate, ctypes.POINTER(wintypes.DWORD))
    kernel.ReadConsoleOutputCharacterW.restype = wintypes.BOOL
    result = subprocess.run([str(executable), "--version"], timeout=60)
    handle = kernel.GetStdHandle(-11)
    info = ConsoleInfo()
    if not kernel.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    count = info.size.x * (info.cursor.y + 1)
    buffer = ctypes.create_unicode_buffer(count + 1)
    received = wintypes.DWORD()
    if not kernel.ReadConsoleOutputCharacterW(handle, buffer, count, Coordinate(0, 0), ctypes.byref(received)):
        raise ctypes.WinError(ctypes.get_last_error())
    output.write_text(json.dumps(dict(code=result.returncode, screen=buffer[:received.value].rstrip())), encoding="utf-8")


def check(executable, expected_version, directory):
    with executable.open("rb") as stream:
        stream.seek(0x3C)
        header = struct.unpack("<I", stream.read(4))[0]
        stream.seek(header + 24 + 68)
        subsystem = struct.unpack("<H", stream.read(2))[0]
    if subsystem != 2:
        raise ValueError(dict(executable=str(executable), subsystem=subsystem))
    output = directory / "cli-console-check.json"
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    subprocess.run([sys.executable, str(Path(__file__).resolve()), str(executable), str(output)],
        creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup, timeout=90, check=True)
    report = json.loads(output.read_text(encoding="utf-8"))
    if report["code"] or expected_version not in report["screen"]:
        raise ValueError(str(output))


if __name__ == "__main__":
    probe(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
