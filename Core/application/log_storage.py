from Core.application.diagnostics import diagnostic
import os
import zipfile

from pathlib import Path
from threading import RLock
from uuid import uuid4


class LogFileDriver:
    def __init__(self) -> None:
        self._lock = RLock()

    def append(self, path: Path, line: str) -> None:
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(line)

    def archive(self, directory: Path, current: Path, batch: int) -> None:
        with self._lock:
            if not directory.is_dir():
                return
            files = sorted((path for path in directory.glob("*.log") if path != current and not path.is_symlink()), key=lambda path: path.stat().st_mtime)
            for offset in range(0, len(files) - batch + 1, batch):
                group = files[offset:offset + batch]
                output = directory / (group[0].stem + "--" + group[-1].stem + ".zip")
                stage = directory / ("." + uuid4().hex + ".part")
                try:
                    with zipfile.ZipFile(stage, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                        for path in group:
                            archive.write(path, path.name)
                    with zipfile.ZipFile(stage) as archive:
                        if archive.testzip() is not None:
                            raise OSError(diagnostic('log_storage.log.archive.integrity.verification.failed'))
                    os.replace(stage, output)
                    for path in group:
                        path.unlink()
                finally:
                    stage.unlink(missing_ok=True)
