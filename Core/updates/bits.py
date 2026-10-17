import ctypes
from collections import deque
from ctypes import wintypes
from hashlib import sha256
from pathlib import Path
from time import monotonic, perf_counter
from uuid import UUID
import socket

from Core.application.diagnostics import diagnostic


class Guid(ctypes.Structure):
    _fields_ = (('data', ctypes.c_ubyte * 16),)

    @classmethod
    def parse(cls, value):
        return cls.from_buffer_copy(UUID(value).bytes_le)


class Progress(ctypes.Structure):
    _fields_ = (('total', ctypes.c_uint64), ('transferred', ctypes.c_uint64), ('files_total', wintypes.ULONG), ('files_transferred', wintypes.ULONG))


def call(pointer, slot, types=(), values=()):
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    function = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *types)(table[slot])
    result = function(pointer, *values)
    if result < 0:
        raise OSError(diagnostic('updates.bits_error', hex(result & 0xffffffff)))
    return result


class Bits:
    def __init__(self):
        self.ole = ctypes.OleDLL('ole32')
        self.ole.CoInitializeEx.argtypes = (ctypes.c_void_p, wintypes.DWORD)
        self.ole.CoInitializeEx.restype = ctypes.c_long
        self.ole.CoCreateInstance.argtypes = (ctypes.POINTER(Guid), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Guid), ctypes.POINTER(ctypes.c_void_p))
        self.ole.CoCreateInstance.restype = ctypes.c_long
        self.ole.CoTaskMemFree.argtypes = (ctypes.c_void_p,)
        self.ole.CoTaskMemFree.restype = None
        self.ole.CoUninitialize.restype = None
        self.manager = ctypes.c_void_p()
        self.initialized = self.ole.CoInitializeEx(None, 0) >= 0
        try:
            self.ole.CoCreateInstance(ctypes.byref(Guid.parse('4991d34b-80a1-4291-83b6-3328366b9097')), None, 4,
                ctypes.byref(Guid.parse('5ce34c0d-0dc9-4c1f-897c-daa1b78cee7c')), ctypes.byref(self.manager))
        except BaseException:
            self.close()
            raise

    def create(self, name, url, destination):
        identity, job = Guid(), ctypes.c_void_p()
        call(self.manager, 3, (wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(Guid), ctypes.POINTER(ctypes.c_void_p)), (name, 0, ctypes.byref(identity), ctypes.byref(job)))
        try:
            call(job, 21, (ctypes.c_int,), (3,))
            call(job, 4, (wintypes.LPCWSTR, wintypes.LPCWSTR), (url, str(Path(destination).resolve())))
            return job
        except BaseException:
            call(job, 8)
            call(job, 2)
            raise

    def cleanup(self, prefix):
        enumeration = ctypes.c_void_p()
        call(self.manager, 5, (wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)), (0, ctypes.byref(enumeration)))
        try:
            while True:
                job, fetched = ctypes.c_void_p(), wintypes.ULONG()
                call(enumeration, 3, (wintypes.ULONG, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.ULONG)), (1, ctypes.byref(job), ctypes.byref(fetched)))
                if not fetched.value:
                    break
                name = ctypes.c_void_p()
                try:
                    call(job, 18, (ctypes.POINTER(ctypes.c_void_p),), (ctypes.byref(name),))
                    if ctypes.wstring_at(name).startswith(prefix):
                        call(job, 8)
                finally:
                    if name.value:
                        self.ole.CoTaskMemFree(name)
                    call(job, 2)
        finally:
            call(enumeration, 2)

    def close(self):
        if self.manager.value:
            call(self.manager, 2)
            self.manager = ctypes.c_void_p()
        if self.initialized:
            self.ole.CoUninitialize()
            self.initialized = False


class CongestionGate:
    def __init__(self):
        self.baseline = None
        self.samples = deque(maxlen=24)
        self.idle_samples = deque(maxlen=8)
        self.good = 0
        self.paused_until = 0.0
        self.allowed = False
        self.route = None

    def observe(self, latency, now, *, route=None):
        if route is not None:
            if self.route is not None and route != self.route:
                self.__init__()
            self.route = route
        if latency is None:
            self.idle_samples.clear()
            self.good = 0
            self.allowed = False
            self.paused_until = now + 10
            return False
        if self.baseline is None:
            self.samples.append(latency)
            if len(self.samples) < 8:
                return False
            self.baseline = sorted(self.samples)[6]
        elif not self.allowed:
            self.idle_samples.append(latency)
            if len(self.idle_samples) == 8:
                idle = sorted(self.idle_samples)
                if idle[1] <= self.baseline + max(.003, self.baseline * .1):
                    self.baseline = min(idle[6], self.baseline * 2 + .003)
                    self.samples.clear()
                    self.samples.extend(self.idle_samples)
                self.idle_samples.clear()
        if latency > self.baseline + max(.003, self.baseline * .1):
            if self.allowed:
                self.idle_samples.clear()
            self.allowed = False
            self.good = 0
            self.paused_until = now + 10
        else:
            self.good += 1
            self.allowed = self.good >= 3 and now >= self.paused_until
            if self.allowed:
                self.samples.append(latency)
                self.baseline = sorted(self.samples)[max(0, (len(self.samples) * 4 - 1) // 5)]
        return self.allowed


class ConnectionProbe:
    def __init__(self, host, port=443):
        self.host = host
        self.port = port
        self.route = None

    def __call__(self):
        start = perf_counter()
        try:
            with socket.create_connection((self.host, self.port), timeout=.75) as connection:
                self.route = connection.family, connection.getsockname()[0]
                return perf_counter() - start
        except OSError:
            return None


def latency(host, port=443):
    return ConnectionProbe(host, port)()


def transfer(root, url, destination, size, cancellation, progress, paused, *, probe=None, bits_factory=Bits):
    from urllib.parse import urlsplit
    host = urlsplit(url).hostname
    probe = probe or ConnectionProbe(host)
    service = bits_factory()
    job = None
    complete = False
    try:
        prefix = 'SerpentineLauncher.Update.' + sha256(str(Path(root).resolve()).encode()).hexdigest()[:20] + '.'
        service.cleanup(prefix)
        job = service.create(prefix + Path(destination).name, url, destination)
        gate = CongestionGate()
        running = False
        next_probe = 0.0
        began = monotonic()
        while True:
            if cancellation.is_paused():
                if running:
                    call(job, 6)
                    running = False
                paused(True)
                cancellation.check()
                next_probe = 0.0
            cancellation.check()
            now = monotonic()
            if now >= next_probe:
                allowed = gate.observe(probe(), monotonic(), route=getattr(probe, 'route', None))
                next_probe = monotonic() + (.5 if gate.baseline is None else 1.0)
                if allowed != running:
                    call(job, 7 if allowed else 6)
                    running = allowed
                paused(not running)
            current, state = Progress(), ctypes.c_int()
            call(job, 12, (ctypes.POINTER(Progress),), (ctypes.byref(current),))
            call(job, 14, (ctypes.POINTER(ctypes.c_int),), (ctypes.byref(state),))
            if current.transferred > size or current.total not in (size, 0xffffffffffffffff):
                raise ValueError(diagnostic('updates.checksum'))
            progress(int(current.transferred), size, int(current.transferred) / max(.001, now - began))
            if state.value == 6:
                call(job, 9)
                complete = True
                return
            if state.value == 4:
                error, context, code = ctypes.c_void_p(), ctypes.c_int(), ctypes.c_long()
                call(job, 15, (ctypes.POINTER(ctypes.c_void_p),), (ctypes.byref(error),))
                try:
                    call(error, 3, (ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_long)), (ctypes.byref(context), ctypes.byref(code)))
                    raise OSError(diagnostic('updates.bits_error', hex(code.value & 0xffffffff)))
                finally:
                    call(error, 2)
            if state.value == 8:
                raise OSError(diagnostic('updates.background_unavailable'))
            cancellation.wait(.1)
    finally:
        if job is not None:
            try:
                if not complete:
                    call(job, 8)
            finally:
                call(job, 2)
        service.close()
