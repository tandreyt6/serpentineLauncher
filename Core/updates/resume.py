import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

from Core.configuration import settings
from Core.application.diagnostics import diagnostic
from Core.updates.version import UPDATER_EXECUTABLE

state = None
plan = None
_adopted = False


def read(path):
    data = Path(path).read_bytes()
    if len(data) > 1048576:
        raise ValueError(diagnostic('updates.client_transfer'))
    return json.loads(data)


def process_path(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        value = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(value))
        if not kernel.QueryFullProcessImageNameW(handle, 0, value, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return Path(value.value).resolve()
    finally:
        kernel.CloseHandle(handle)


def initialize(arguments):
    global state, plan
    ticket = settings.ROOT / 'cache/update-session.json'
    explicit = arguments[:1] == ['--resume-update']
    if not explicit and arguments or os.name != 'nt':
        return arguments
    try:
        saved = read(ticket)
        candidate = Path(arguments[1] if explicit and len(arguments) == 2 else saved['plan']).resolve()
        if candidate != Path(saved['plan']).resolve():
            raise ValueError(diagnostic('updates.client_transfer'))
        data = read(str(candidate) + '.resume')
        if Path(data['target']).resolve() != settings.ROOT.resolve() or data['token'] != saved['token'] or len(data['clients']) > 100:
            raise ValueError(diagnostic('updates.client_transfer'))
        if process_path(data['updaterPid']) != candidate.parent / UPDATER_EXECUTABLE:
            raise ValueError(diagnostic('updates.client_transfer'))
        state, plan = data, candidate
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        if explicit:
            raise ValueError(diagnostic('updates.client_transfer')) from None
    return [] if explicit else arguments


def adopt(core):
    global _adopted
    if state is not None and not _adopted:
        from Core.game.launch import LaunchManager
        core.app.get('launch', LaunchManager).adopt_clients(state['updaterPid'], state['clients'])
        _adopted = True


def acknowledge():
    if state is None or not _adopted:
        return
    destination = Path(str(plan) + '.restored')
    pending = destination.with_suffix('.pending')
    pending.write_text(json.dumps(dict(pid=os.getpid(), token=state['token'])), encoding='utf-8')
    pending.replace(destination)
    ticket = settings.ROOT / 'cache/update-session.json'
    if ticket.is_file() and read(ticket)['token'] == state['token']:
        ticket.unlink()
