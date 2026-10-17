from Core.application.diagnostics import diagnostic
import ctypes
import getpass
import hashlib
import json
import os
import tempfile

from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from dataclasses import asdict
from multiprocessing import AuthenticationError
from multiprocessing.connection import Client, Listener
from pathlib import Path
from threading import Event, Thread, RLock
from time import monotonic, sleep
from typing import Callable

from Core.configuration.settings import APP_ID, IPC_DIRECTORY_NAME, IPC_MAXIMUM_BYTES, IPC_POLL_INTERVAL_SECONDS, IPC_READY_TIMEOUT_SECONDS, IPC_RESPONSE_TIMEOUT_SECONDS, IPC_WORKERS
from Core.cli.contracts import CliRequest, CliResponse


def ipc_failure(request: CliRequest, message: str) -> CliResponse:
    if request.format == "json":
        return CliResponse(1, json.dumps({"ok": False, "error": message}) + "\n")
    return CliResponse(1, "", message + "\n")


class InstanceDriver:
    _owned_names: set[str] = set()
    _owners_lock = RLock()

    def __init__(self, identity: str = APP_ID, directory: Path | None = None) -> None:
        user = getpass.getuser() + str(Path.home())
        self._identity = hashlib.sha256((identity + user).encode()).hexdigest()[:32]
        self._directory = directory or Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "state"))) / IPC_DIRECTORY_NAME
        self._directory.mkdir(parents=True, exist_ok=True)
        self._record = self._directory / (self._identity + ".json")
        self._listener = None
        self._pool = None
        self._thread = None
        self._stop = Event()
        self._handler = None
        self._handle = None
        self._descriptor = None
        self._authkey = None
        self._owns_mutex = False
        if os.name == "nt":
            self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            self._kernel.CreateMutexW.restype = wintypes.HANDLE
            self._kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            self._kernel.CloseHandle.restype = wintypes.BOOL
            self._kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self._kernel.WaitForSingleObject.restype = wintypes.DWORD
            self._kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
            self._kernel.ReleaseMutex.restype = wintypes.BOOL
            self._handle = self._kernel.CreateMutexW(None, True, "Global\\" + self._identity)
            if not self._handle:
                raise ctypes.WinError(ctypes.get_last_error())
            existed = ctypes.get_last_error() == 183
            with self._owners_lock:
                self.primary = not existed
                if existed and self._identity not in self._owned_names:
                    self.primary = self._kernel.WaitForSingleObject(self._handle, 0) in (0, 128)
                if self.primary:
                    self._owned_names.add(self._identity)
                    self._owns_mutex = True
        else:
            self._descriptor = os.open(self._directory / (self._identity + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
            libc = ctypes.CDLL(None, use_errno=True)
            libc.flock.argtypes = (ctypes.c_int, ctypes.c_int)
            libc.flock.restype = ctypes.c_int
            self.primary = libc.flock(self._descriptor, 2 | 4) == 0

    def start(self, handler: Callable[[CliRequest], CliResponse]) -> None:
        if not self.primary or self._listener is not None:
            raise RuntimeError(diagnostic('instance.only.the.primary.instance.can.serve'))
        self._handler = handler
        self._authkey = os.urandom(32)
        self._listener = Listener(("127.0.0.1", 0), family="AF_INET", authkey=self._authkey)
        descriptor, temporary = tempfile.mkstemp(prefix=".ipc-", dir=self._directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({"address": self._listener.address, "key": self._authkey.hex(), "pid": os.getpid()}, stream)
            os.replace(temporary, self._record)
            if os.name != "nt":
                self._record.chmod(0o600)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self._pool = ThreadPoolExecutor(max_workers=IPC_WORKERS, thread_name_prefix="launcher-ipc")
        self._thread = Thread(target=self._accept, name="launcher-ipc-listener", daemon=True)
        self._thread.start()

    def _accept(self) -> None:
        listener = self._listener
        while not self._stop.is_set():
            try:
                connection = listener.accept()
                if self._stop.is_set():
                    connection.close()
                    break
                self._pool.submit(self._serve, connection)
            except (OSError, EOFError, ValueError, AuthenticationError):
                if self._stop.is_set():
                    break

    def _serve(self, connection) -> None:
        with connection:
            try:
                if not connection.poll(IPC_READY_TIMEOUT_SECONDS):
                    return
                value = json.loads(connection.recv_bytes(IPC_MAXIMUM_BYTES))
                fields = tuple((str(name), str(value)) for name, value in value.get("fields", ()))
                request = CliRequest(value["action"], value.get("key", ""), value.get("value", ""), fields, value.get("format", "text"), bool(value.get("preview", False)))
                response = self._handler(request)
                data = json.dumps(asdict(response), ensure_ascii=False).encode()
                if len(data) > IPC_MAXIMUM_BYTES:
                    data = json.dumps(asdict(ipc_failure(request, "Response exceeds IPC size limit"))).encode()
                connection.send_bytes(data)
            except (OSError, EOFError, ValueError, KeyError, TypeError):
                return

    def forward(self, request: CliRequest) -> CliResponse:
        deadline = monotonic() + IPC_READY_TIMEOUT_SECONDS
        connection = None
        while connection is None:
            try:
                value = json.loads(self._record.read_text(encoding="utf-8"))
                connection = Client(tuple(value["address"]), family="AF_INET", authkey=bytes.fromhex(value["key"]))
            except (OSError, EOFError, ValueError, KeyError, AuthenticationError):
                if monotonic() >= deadline:
                    return ipc_failure(request, "The primary launcher did not become available")
                sleep(IPC_POLL_INTERVAL_SECONDS)
        try:
            with connection:
                data = json.dumps(asdict(request)).encode()
                if len(data) > IPC_MAXIMUM_BYTES:
                    return ipc_failure(request, "Request exceeds IPC size limit")
                connection.send_bytes(data)
                if not connection.poll(IPC_RESPONSE_TIMEOUT_SECONDS):
                    return ipc_failure(request, "The primary launcher response timed out")
                return CliResponse(**json.loads(connection.recv_bytes(IPC_MAXIMUM_BYTES)))
        except (OSError, EOFError, ValueError, KeyError, TypeError):
            return ipc_failure(request, "The primary launcher connection was interrupted")

    def close(self) -> None:
        self._stop.set()
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
        if self.primary and self._authkey is not None and self._record.exists():
            try:
                value = json.loads(self._record.read_text(encoding="utf-8"))
                if value.get("key") == self._authkey.hex():
                    self._record.unlink()
            except (OSError, ValueError, TypeError):
                pass
        if self._handle is not None:
            if self._owns_mutex:
                self._kernel.ReleaseMutex(self._handle)
                with self._owners_lock:
                    self._owned_names.discard(self._identity)
                self._owns_mutex = False
            self._kernel.CloseHandle(self._handle)
            self._handle = None
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None
