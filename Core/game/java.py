from Core.application.diagnostics import diagnostic
import ctypes
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from Core.application.contracts import CoreError, JavaOverrides, JavaSettings
from Core.game.process_manager import ProcessDriver
from Core.game.processes import ProcessSpec
from Core.application.router import AppManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager
from Core.game.java_discovery import java_candidates


@dataclass(frozen=True)
class JavaRuntime:
    executable: Path
    major_version: int
    bits: int


class MemoryStatus(ctypes.Structure):
    _fields_ = (("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong), ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong), ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong))


def physical_memory_mb() -> int:
    if os.name == "nt":
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError(diagnostic('java.cannot.determine.physical.memory'))
        return status.total_phys // (1024 * 1024)
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024)


def merge_java(global_settings: JavaSettings, overrides: JavaOverrides) -> JavaSettings:
    return JavaSettings(overrides.executable if overrides.executable is not None else global_settings.executable, overrides.minimum_memory_mb if overrides.minimum_memory_mb is not None else global_settings.minimum_memory_mb, overrides.maximum_memory_mb if overrides.maximum_memory_mb is not None else global_settings.maximum_memory_mb, overrides.extra_arguments if overrides.extra_arguments is not None else global_settings.extra_arguments)


def parse_java_runtime(executable: Path, output: str) -> JavaRuntime:
    version = re.search(r'(?:java|openjdk) version "([0-9]+)(?:\.([0-9]+))?', output)
    if version is None:
        version = re.search(r"java.version\s*=\s*([0-9]+)(?:\.([0-9]+))?", output)
    bits = re.search(r"sun.arch.data.model\s*=\s*(32|64)", output)
    if version is None or bits is None:
        raise CoreError(diagnostic('java.executable.did.not.identify.itself.as'))
    major = int(version.group(2)) if version.group(1) == "1" else int(version.group(1))
    return JavaRuntime(executable, major, int(bits.group(1)))


def select_java_runtime(runtimes: tuple[JavaRuntime, ...], required_major: int | None = None) -> JavaRuntime:
    candidates = tuple(runtime for runtime in runtimes if required_major is None or runtime.major_version >= required_major)
    if not candidates:
        raise CoreError(diagnostic('java.no.installed.java.runtime.meets.the'))
    if required_major is None:
        return max(candidates, key=java_preference)
    preferred = tuple(runtime for runtime in candidates if runtime.bits == 64) or candidates
    return min(preferred, key=java_version)


def java_preference(runtime: JavaRuntime) -> tuple[int, int]:
    return runtime.bits, runtime.major_version


def java_version(runtime: JavaRuntime) -> int:
    return runtime.major_version


class JavaManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config

    def validate_settings(self, settings: JavaSettings) -> JavaSettings:
        maximum = self._config.available_memory_mb or physical_memory_mb()
        if settings.minimum_memory_mb < self._config.minimum_memory_mb or settings.maximum_memory_mb < settings.minimum_memory_mb or settings.maximum_memory_mb > maximum:
            raise CoreError(diagnostic('java.jvm.memory.must.be.within.physical'))
        if any(argument.startswith(("-Xmx", "-Xms")) or argument in ("-cp", "-classpath", "--class-path", "-jar") for argument in settings.extra_arguments):
            raise CoreError(diagnostic('java.memory.and.classpath.must.use.their'))
        executable = settings.executable
        if not executable.is_absolute():
            if len(executable.parts) == 1:
                found = shutil.which(str(executable))
                if found:
                    executable = Path(found)
                else:
                    executable = self._config.root / executable
            else:
                executable = self._config.root / executable
        executable = executable.resolve()
        if not executable.is_file():
            raise CoreError(diagnostic('java.java.executable.does.not.exist'))
        return JavaSettings(executable, settings.minimum_memory_mb, settings.maximum_memory_mb, settings.extra_arguments)

    def probe(self, executable: Path) -> JavaRuntime:
        files = self._app.get("files", FileManager)
        relative_log = f"{self._config.logs_directory}/{self._config.java_probes_directory}/{uuid4().hex}.log"
        process = self._app.get("processes", ProcessDriver).spawn(ProcessSpec((str(executable), "-XshowSettings:properties", "-version"), self._config.root.resolve(), files.path(relative_log)))
        try:
            if process.wait(timeout=self._config.java_probe_timeout) != 0:
                raise CoreError(diagnostic('java.java.runtime.verification.failed'))
            output = files.read(relative_log).decode("utf-8", errors="replace")
            return parse_java_runtime(executable, output)
        finally:
            process.dispose()

    def discover(self) -> tuple[JavaRuntime, ...]:
        def probe(executable):
            try:
                return self.probe(executable)
            except (CoreError, OSError, subprocess.TimeoutExpired):
                return None
        with ThreadPoolExecutor(max_workers=self._config.java_discovery_workers) as executor:
            runtimes = tuple(runtime for runtime in executor.map(probe, java_candidates()) if runtime is not None)
        return tuple(sorted(runtimes, key=java_preference, reverse=True))

    def close(self) -> None:
        pass
