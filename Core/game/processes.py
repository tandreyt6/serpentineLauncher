from Core.application.diagnostics import diagnostic
import ctypes
import os
import signal
import subprocess
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class ProcessSpec:
    argv: tuple[str, ...] = field(repr=False)
    cwd: Path
    log_path: Path


@dataclass(frozen=True)
class ProcessPolicy:
    wait_interval_seconds: float = 0.05
    cleanup_timeout_seconds: float = 10.0
    job_snapshot_attempts: int = 8

    def __post_init__(self) -> None:
        if self.wait_interval_seconds <= 0 or self.cleanup_timeout_seconds <= 0 or self.job_snapshot_attempts < 1:
            raise ValueError(diagnostic('processes.process.timing.values.and.snapshot.attempts'))


class ManagedProcess(Protocol):
    @property
    def pid(self) -> int: ...

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def request_close(self) -> bool: ...

    def kill(self) -> None: ...

    def dispose(self) -> None: ...


class ProcessAdapter(Protocol):
    def spawn(self, spec: ProcessSpec) -> ManagedProcess: ...


def validate_process_spec(spec: ProcessSpec) -> None:
    if not spec.argv or any(not isinstance(argument, str) or "\x00" in argument for argument in spec.argv):
        raise ValueError(diagnostic('processes.process.arguments.must.contain.an.executable'))
    if not spec.argv[0]:
        raise ValueError(diagnostic('processes.process.executable.must.not.be.empty'))
    if not spec.cwd.is_dir():
        raise ValueError(diagnostic('processes.process.working.directory.does.not.exist'))


class PosixManagedProcess:
    def __init__(self, process: subprocess.Popen[bytes], log: BinaryIO, policy: ProcessPolicy) -> None:
        self._process = process
        self._log = log
        self._policy = policy
        self._disposed = False
        self._lock = threading.RLock()

    @property
    def pid(self) -> int:
        return self._process.pid

    def poll(self) -> int | None:
        return self._process.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self._process.wait(timeout=timeout)

    def request_close(self) -> bool:
        if self.poll() is not None:
            return False
        return self._signal_group(signal.SIGTERM)

    def kill(self) -> None:
        self._signal_group(signal.SIGKILL)

    def _signal_group(self, number: int) -> bool:
        with self._lock:
            if self._disposed:
                return False
            try:
                os.killpg(self.pid, number)
            except ProcessLookupError:
                return False
            return True

    def dispose(self) -> None:
        with self._lock:
            if self._disposed:
                return
            self.kill()
            try:
                self.wait(self._policy.cleanup_timeout_seconds)
            finally:
                self._log.close()
                self._disposed = True


class PosixProcessAdapter:
    def __init__(self, policy: ProcessPolicy = ProcessPolicy()) -> None:
        self._policy = policy

    def spawn(self, spec: ProcessSpec) -> ManagedProcess:
        if os.name == "nt":
            raise OSError(diagnostic('processes.posix.process.adapter.is.unavailable.on'))
        validate_process_spec(spec)
        spec.log_path.parent.mkdir(parents=True, exist_ok=True)
        log = spec.log_path.open("ab", buffering=0)
        try:
            process = subprocess.Popen(spec.argv, cwd=spec.cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except BaseException:
            log.close()
            raise
        return PosixManagedProcess(process, log, self._policy)


class SecurityAttributes(ctypes.Structure):
    _fields_ = (("length", wintypes.DWORD), ("descriptor", wintypes.LPVOID), ("inherit", wintypes.BOOL))


class StartupInfo(ctypes.Structure):
    _fields_ = (("size", wintypes.DWORD), ("reserved", wintypes.LPWSTR), ("desktop", wintypes.LPWSTR), ("title", wintypes.LPWSTR), ("x", wintypes.DWORD), ("y", wintypes.DWORD), ("x_size", wintypes.DWORD), ("y_size", wintypes.DWORD), ("x_chars", wintypes.DWORD), ("y_chars", wintypes.DWORD), ("fill", wintypes.DWORD), ("flags", wintypes.DWORD), ("show", wintypes.WORD), ("reserved_size", wintypes.WORD), ("reserved_bytes", ctypes.POINTER(ctypes.c_byte)), ("stdin", wintypes.HANDLE), ("stdout", wintypes.HANDLE), ("stderr", wintypes.HANDLE))


class StartupInfoEx(ctypes.Structure):
    _fields_ = (("startup", StartupInfo), ("attributes", wintypes.LPVOID))


class ProcessInformation(ctypes.Structure):
    _fields_ = (("process", wintypes.HANDLE), ("thread", wintypes.HANDLE), ("pid", wintypes.DWORD), ("tid", wintypes.DWORD))


class BasicJobLimits(ctypes.Structure):
    _fields_ = (("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64), ("flags", wintypes.DWORD), ("minimum_working_set", ctypes.c_size_t), ("maximum_working_set", ctypes.c_size_t), ("active_process_limit", wintypes.DWORD), ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD))


class IoCounters(ctypes.Structure):
    _fields_ = (("read_ops", ctypes.c_uint64), ("write_ops", ctypes.c_uint64), ("other_ops", ctypes.c_uint64), ("read_bytes", ctypes.c_uint64), ("write_bytes", ctypes.c_uint64), ("other_bytes", ctypes.c_uint64))


class ExtendedJobLimits(ctypes.Structure):
    _fields_ = (("basic", BasicJobLimits), ("io", IoCounters), ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t), ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t))


class WindowsApi:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError(diagnostic('processes.windows.process.adapter.is.unavailable.on'))
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.window_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self._declare(self.kernel.CreateJobObjectW, (wintypes.LPVOID, wintypes.LPCWSTR), wintypes.HANDLE)
        self._declare(self.kernel.SetInformationJobObject, (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD), wintypes.BOOL)
        self._declare(self.kernel.AssignProcessToJobObject, (wintypes.HANDLE, wintypes.HANDLE), wintypes.BOOL)
        self._declare(self.kernel.TerminateJobObject, (wintypes.HANDLE, wintypes.UINT), wintypes.BOOL)
        self._declare(self.kernel.QueryInformationJobObject, (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL)
        self._declare(self.kernel.CloseHandle, (wintypes.HANDLE,), wintypes.BOOL)
        self._declare(self.kernel.CreateFileW, (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(SecurityAttributes), wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE), wintypes.HANDLE)
        self._declare(self.kernel.InitializeProcThreadAttributeList, (wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)), wintypes.BOOL)
        self._declare(self.kernel.UpdateProcThreadAttribute, (wintypes.LPVOID, wintypes.DWORD, ctypes.c_size_t, wintypes.LPVOID, ctypes.c_size_t, wintypes.LPVOID, wintypes.LPVOID), wintypes.BOOL)
        self._declare(self.kernel.DeleteProcThreadAttributeList, (wintypes.LPVOID,), None)
        self._declare(self.kernel.CreateProcessW, (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(StartupInfoEx), ctypes.POINTER(ProcessInformation)), wintypes.BOOL)
        self._declare(self.kernel.ResumeThread, (wintypes.HANDLE,), wintypes.DWORD)
        self._declare(self.kernel.TerminateProcess, (wintypes.HANDLE, wintypes.UINT), wintypes.BOOL)
        self._declare(self.kernel.WaitForSingleObject, (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD)
        self._declare(self.kernel.GetExitCodeProcess, (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL)
        self._declare(self.kernel.GetCurrentProcess, (), wintypes.HANDLE)
        self._declare(self.kernel.OpenProcess, (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE)
        self._declare(self.kernel.DuplicateHandle, (wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.BOOL)
        self._declare(self.user.EnumWindows, (self.window_callback, wintypes.LPARAM), wintypes.BOOL)
        self._declare(self.user.GetWindowThreadProcessId, (wintypes.HWND, ctypes.POINTER(wintypes.DWORD)), wintypes.DWORD)
        self._declare(self.user.PostMessageW, (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM), wintypes.BOOL)

    def _declare(self, function: object, arguments: tuple[object, ...], result: object) -> None:
        function.argtypes = arguments
        function.restype = result

    def checked(self, success: object) -> None:
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())


class WindowsManagedProcess:
    def __init__(self, api: WindowsApi, pid: int, process: int, job: int, policy: ProcessPolicy) -> None:
        self._api = api
        self._pid = pid
        self._process = process
        self._job = job
        self._policy = policy
        self._exit_code: int | None = None
        self._disposed = False
        self.detached = False
        self._lock = threading.RLock()

    @property
    def pid(self) -> int:
        return self._pid

    def poll(self) -> int | None:
        with self._lock:
            if self._exit_code is not None:
                return self._exit_code
            if self._disposed:
                raise RuntimeError(diagnostic('processes.process.ownership.has.been.disposed'))
            status = self._api.kernel.WaitForSingleObject(self._process, 0)
            if status == 258:
                return None
            if status != 0:
                raise ctypes.WinError(ctypes.get_last_error())
            code = wintypes.DWORD()
            self._api.checked(self._api.kernel.GetExitCodeProcess(self._process, ctypes.byref(code)))
            self._exit_code = int(code.value)
            return self._exit_code

    def wait(self, timeout: float | None = None) -> int:
        deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
        while True:
            if self.detached:
                return 0
            code = self.poll()
            if code is not None:
                return code
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            delay = self._policy.wait_interval_seconds
            if deadline is not None:
                delay = min(delay, max(0.0, deadline - time.monotonic()))
            time.sleep(delay)

    def request_close(self) -> bool:
        with self._lock:
            if self._disposed or self.poll() is not None:
                return False
            process_ids = self._job_process_ids()
            posted: list[bool] = []

            def close_window(window: int, argument: int) -> bool:
                owner = wintypes.DWORD()
                self._api.user.GetWindowThreadProcessId(window, ctypes.byref(owner))
                if owner.value in process_ids:
                    posted.append(bool(self._api.user.PostMessageW(window, 0x0010, 0, 0)))
                return True

            callback = self._api.window_callback(close_window)
            self._api.checked(self._api.user.EnumWindows(callback, 0))
            return any(posted)

    def _job_process_ids(self) -> frozenset[int]:
        capacity = 16
        for attempt in range(self._policy.job_snapshot_attempts):
            buffer = ctypes.create_string_buffer(8 + capacity * ctypes.sizeof(ctypes.c_size_t))
            returned = wintypes.DWORD()
            success = self._api.kernel.QueryInformationJobObject(self._job, 3, ctypes.cast(buffer, wintypes.LPVOID), len(buffer), ctypes.byref(returned))
            if success:
                count = wintypes.DWORD.from_buffer(buffer, 4).value
                values = (ctypes.c_size_t * count).from_buffer(buffer, 8)
                return frozenset(int(value) for value in values)
            error = ctypes.get_last_error()
            if error != 234:
                raise ctypes.WinError(error)
            capacity = max(capacity * 2, wintypes.DWORD.from_buffer(buffer).value)
        raise RuntimeError(diagnostic('processes.process.group.changed.too.quickly.to'))

    def kill(self) -> None:
        with self._lock:
            if not self._disposed:
                self._api.checked(self._api.kernel.TerminateJobObject(self._job, 1))

    def dispose(self) -> None:
        with self._lock:
            if self._disposed:
                return
            if self.detached:
                self._api.kernel.CloseHandle(self._process)
                self._api.kernel.CloseHandle(self._job)
                self._disposed = True
                return
            self.kill()
            try:
                self.wait(self._policy.cleanup_timeout_seconds)
            finally:
                self._api.kernel.CloseHandle(self._process)
                self._api.kernel.CloseHandle(self._job)
                self._disposed = True

    def duplicate(self, target_pid):
        with self._lock:
            if self._disposed or self.detached or self.poll() is not None:
                raise RuntimeError(diagnostic('updates.client_transfer'))
            kernel = self._api.kernel
            target = kernel.OpenProcess(0x0040, False, target_pid)
            self._api.checked(target)
            duplicated = []
            try:
                for handle in (self._process, self._job):
                    output = wintypes.HANDLE()
                    self._api.checked(kernel.DuplicateHandle(kernel.GetCurrentProcess(), handle, target, ctypes.byref(output), 0, False, 2))
                    duplicated.append(output.value)
            finally:
                kernel.CloseHandle(target)
            return dict(pid=self.pid, process=duplicated[0], job=duplicated[1])

    @classmethod
    def adopt(cls, api, source_pid, values, policy=ProcessPolicy()):
        kernel = api.kernel
        source = kernel.OpenProcess(0x0040, False, source_pid)
        api.checked(source)
        handles = []
        try:
            for name in ('process', 'job'):
                output = wintypes.HANDLE()
                api.checked(kernel.DuplicateHandle(source, values[name], kernel.GetCurrentProcess(), ctypes.byref(output), 0, False, 2))
                handles.append(output.value)
        except BaseException:
            for handle in handles:
                kernel.CloseHandle(handle)
            raise
        finally:
            kernel.CloseHandle(source)
        return cls(api, values['pid'], handles[0], handles[1], policy)


class WindowsProcessAdapter:
    def __init__(self, policy: ProcessPolicy = ProcessPolicy(), api: WindowsApi | None = None) -> None:
        self._policy = policy
        self._api = api if api is not None else WindowsApi()

    def spawn(self, spec: ProcessSpec) -> ManagedProcess:
        validate_process_spec(spec)
        spec.log_path.parent.mkdir(parents=True, exist_ok=True)
        api = self._api
        kernel = api.kernel
        job = kernel.CreateJobObjectW(None, None)
        api.checked(job)
        process = ProcessInformation()
        log = None
        stdin = None
        attributes = None
        transferred = False
        try:
            limits = ExtendedJobLimits()
            limits.basic.flags = 0x00002000
            api.checked(kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
            security = SecurityAttributes(ctypes.sizeof(SecurityAttributes), None, True)
            log = kernel.CreateFileW(str(spec.log_path.resolve()), 0x00000004, 0x00000001 | 0x00000002, ctypes.byref(security), 4, 0x00000080, None)
            if log == ctypes.c_void_p(-1).value:
                log = None
                raise ctypes.WinError(ctypes.get_last_error())
            stdin = kernel.CreateFileW("NUL", 0x80000000, 0x00000001 | 0x00000002, ctypes.byref(security), 3, 0x00000080, None)
            if stdin == ctypes.c_void_p(-1).value:
                stdin = None
                raise ctypes.WinError(ctypes.get_last_error())
            attribute_size = ctypes.c_size_t()
            kernel.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(attribute_size))
            storage = ctypes.create_string_buffer(attribute_size.value)
            attribute_pointer = ctypes.cast(storage, wintypes.LPVOID)
            api.checked(kernel.InitializeProcThreadAttributeList(attribute_pointer, 1, 0, ctypes.byref(attribute_size)))
            attributes = attribute_pointer
            handles = (wintypes.HANDLE * 2)(stdin, log)
            api.checked(kernel.UpdateProcThreadAttribute(attributes, 0, 0x00020002, ctypes.cast(handles, wintypes.LPVOID), ctypes.sizeof(handles), None, None))
            startup = StartupInfoEx()
            startup.startup.size = ctypes.sizeof(startup)
            startup.startup.flags = 0x00000100
            startup.startup.stdin = stdin
            startup.startup.stdout = log
            startup.startup.stderr = log
            startup.attributes = attributes
            command = ctypes.create_unicode_buffer(subprocess.list2cmdline(spec.argv))
            flags = 0x00000004 | 0x00080000 | 0x08000000
            api.checked(kernel.CreateProcessW(None, command, None, None, True, flags, None, str(spec.cwd.resolve()), ctypes.byref(startup), ctypes.byref(process)))
            api.checked(kernel.AssignProcessToJobObject(job, process.process))
            if kernel.ResumeThread(process.thread) == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            result = WindowsManagedProcess(api, int(process.pid), process.process, job, self._policy)
            transferred = True
            return result
        finally:
            if process.thread:
                kernel.CloseHandle(process.thread)
            if not transferred:
                if process.process:
                    kernel.TerminateProcess(process.process, 1)
                    kernel.WaitForSingleObject(process.process, int(self._policy.cleanup_timeout_seconds * 1000))
                    kernel.CloseHandle(process.process)
                kernel.CloseHandle(job)
            if attributes:
                kernel.DeleteProcThreadAttributeList(attributes)
            if stdin:
                kernel.CloseHandle(stdin)
            if log:
                kernel.CloseHandle(log)


def default_process_adapter(policy: ProcessPolicy = ProcessPolicy()) -> ProcessAdapter:
    return WindowsProcessAdapter(policy) if os.name == "nt" else PosixProcessAdapter(policy)
