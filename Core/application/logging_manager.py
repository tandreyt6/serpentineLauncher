from Core.application.diagnostics import diagnostic
import os

from datetime import datetime
from threading import RLock, current_thread

from Core.application.log_storage import LogFileDriver
from Core.application.router import AppManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager


class LogManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._lock = RLock()
        self._mode = "normal"
        self._batch = 5
        self._started = False
        self._filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + str(os.getpid()) + ".log"

    def configure(self, mode: str, batch: int) -> None:
        if mode not in ("normal", "verbose") or batch not in (5, 10):
            raise ValueError(diagnostic('logging_manager.invalid.logging.settings'))
        with self._lock:
            if batch != self._batch:
                self._started = False
            self._mode, self._batch = mode, batch

    def write(self, message: str, level: str = "INFO") -> None:
        with self._lock:
            if level == "DEBUG" and self._mode != "verbose":
                return
            files = self._app.get("files", FileManager)
            driver = self._app.get("log_files", LogFileDriver)
            directory = files.path(self._config.logs_directory)
            path = files.path(self._config.logs_directory + "/" + self._filename)
            if not self._started:
                driver.archive(directory, path, self._batch)
                self._started = True
            stamp = datetime.now().isoformat(timespec="milliseconds")
            driver.append(path, f"{stamp} [{level}] [{current_thread().name}] {message}\n")

    def close(self) -> None:
        pass
