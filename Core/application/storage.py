from Core.application.diagnostics import diagnostic
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from threading import RLock
from typing import BinaryIO
from uuid import uuid4

from Core.application.contracts import Artifact, CoreError, Digest
from Core.application.settings import CoreConfig
from Core.application.tasks import Cancellation


def safe_identifier(value: str) -> str:
    if not value or value in (".", "..") or not value.isascii() or re.search(r'[<>:"/\\|?*\s\x00-\x1f]', value) or value.endswith((".", " ")):
        raise CoreError(diagnostic('storage.invalid.portable.identifier'))
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{x}" for x in range(1, 10)), *(f"LPT{x}" for x in range(1, 10))}:
        raise CoreError(diagnostic('storage.reserved.windows.identifier'))
    return value


def checked_relative(value: str) -> PurePosixPath:
    if not value or "\\" in value or ":" in value or "\x00" in value:
        raise CoreError(diagnostic('storage.invalid.relative.path'))
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in (".", "..") for part in value.split("/")):
        raise CoreError(diagnostic('storage.path.escapes.launcher.root'))
    for part in path.parts:
        if re.search(r'[<>:"|?*\x00-\x1f]', part) or part.endswith((".", " ")):
            raise CoreError(diagnostic('storage.invalid.portable.path.component'))
        if part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{x}" for x in range(1, 10)), *(f"LPT{x}" for x in range(1, 10))}:
            raise CoreError(diagnostic('storage.reserved.windows.path.component'))
    return path


def resolved_path(path: Path) -> Path:
    resolved = str(path.resolve())
    if os.name == "nt":
        if resolved.startswith("\\\\?\\UNC\\"):
            resolved = "\\\\" + resolved[8:]
        elif resolved.startswith("\\\\?\\"):
            resolved = resolved[4:]
    return Path(resolved)


@dataclass(frozen=True)
class NativeArchive:
    relative_path: str
    excludes: tuple[str, ...] = ("META-INF/",)


class FileManager:
    def __init__(self, config: CoreConfig) -> None:
        self._config = config
        self._root = resolved_path(config.root)
        self._lock = RLock()
        self._stages: dict[str, tuple[Path, Path, BinaryIO]] = {}

    def path(self, relative_path: str) -> Path:
        relative = checked_relative(relative_path)
        target = resolved_path(self._root.joinpath(*relative.parts))
        if not target.is_relative_to(self._root) or target == self._root:
            raise CoreError(diagnostic('storage.path.escapes.launcher.root'))
        return target

    def exists(self, relative_path: str) -> bool:
        return self.path(relative_path).is_file()

    def is_directory(self, relative_path: str) -> bool:
        return self.path(relative_path).is_dir()

    def entries(self, relative_path: str, recursive: bool = False) -> tuple[tuple[str, bool, str], ...]:
        return tuple(sorted(self.iter_entries(relative_path, recursive)))

    def iter_entries(self, relative_path: str, recursive: bool = False, exclude: tuple[str, ...] = ()):
        target = self.path(relative_path)
        if not target.is_dir():
            return
        def failed(error):
            raise error
        def descendants():
            for directory, folders, names in os.walk(target, onerror=failed, followlinks=False):
                parent = Path(directory)
                folders[:] = [name for name in folders if not (parent / name).is_symlink() and not (parent == target and name.casefold() in {value.casefold() for value in exclude})]
                for name in sorted(folders + names):
                    yield parent / name
        iterator = descendants() if recursive else target.iterdir()
        count = 0
        for entry in iterator:
            if entry.is_symlink() or not resolved_path(entry).is_relative_to(target):
                continue
            count += 1
            if count > self._config.mod_scan_entries:
                raise CoreError(diagnostic('storage.directory.listing.exceeds.configured.limit'))
            yield entry.relative_to(target).as_posix(), entry.is_dir(), str(entry.stat().st_mtime)

    def remove_file(self, relative_path: str) -> None:
        self.path(relative_path).unlink(missing_ok=True)

    def mod_digests(self, relative_path: str, cancellation: Cancellation, maximum_bytes: int | None = None) -> tuple[str, str]:
        digest512, digest1 = hashlib.sha512(), hashlib.sha1()
        size = 0
        with self.path(relative_path).open("rb") as stream:
            while chunk := stream.read(self._config.chunk_bytes):
                cancellation.check()
                size += len(chunk)
                if size > (self._config.mod_jar_bytes if maximum_bytes is None else maximum_bytes):
                    raise CoreError(diagnostic('storage.mod.archive.exceeds.size.limit'))
                digest512.update(chunk)
                digest1.update(chunk)
        return digest512.hexdigest(), digest1.hexdigest()

    def rename_file(self, source: str, destination: str) -> None:
        target = self.path(destination)
        if target.exists():
            raise CoreError(diagnostic('storage.destination.already.exists'))
        origin = self.path(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        origin.rename(target)

    def import_file(self, source: Path, artifact: Artifact, cancellation: Cancellation, maximum_bytes: int | None = None) -> None:
        self.validate_import_file(source, maximum_bytes)
        token = self.begin(artifact.relative_path)
        try:
            with source.open("rb") as stream:
                while chunk := stream.read(self._config.chunk_bytes):
                    cancellation.check()
                    self.append(token, chunk)
            self.commit(token, artifact, cancellation)
        finally:
            self.discard(token)

    def validate_import_file(self, source: Path, maximum_bytes: int | None = None) -> None:
        if not source.is_file() or source.is_symlink() or source.stat().st_size > (maximum_bytes or self._config.mod_jar_bytes):
            raise CoreError(diagnostic('storage.import.file.is.missing.or.oversized'))

    def import_plan(self, source: Path, directory: str, cancellation: Cancellation) -> tuple[tuple[Path, str, bool], ...]:
        if not source.is_dir() or source.is_symlink():
            raise CoreError(diagnostic('storage.import.folder.is.missing.or.a'))
        checked_relative(source.name)
        base = (directory + "/" if directory else "") + source.name
        if self.path(base).exists():
            raise CoreError(diagnostic('storage.import.destination.folder.already.exists'))
        result = [(source, base, True)]
        total = 0
        for entry in source.rglob("*"):
            cancellation.check()
            if entry.is_symlink() or not resolved_path(entry).is_relative_to(resolved_path(source)):
                raise CoreError(diagnostic('storage.import.folder.contains.a.symbolic.link'))
            relative = entry.relative_to(source).as_posix()
            checked_relative(relative)
            folder = entry.is_dir()
            if not folder:
                self.validate_import_file(entry, self._config.import_file_bytes)
                total += entry.stat().st_size
            result.append((entry, base + "/" + relative, folder))
            if len(result) > self._config.mod_scan_entries or total > self._config.import_total_bytes:
                raise CoreError(diagnostic('storage.import.folder.exceeds.configured.limits'))
        return tuple(result)

    def external_directory(self, source: Path) -> bool:
        return source.is_dir()

    def size(self, relative_path: str) -> int:
        return self.path(relative_path).stat().st_size

    def ensure_directory(self, relative_path: str) -> Path:
        target = self.path(relative_path)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def verify(self, artifact: Artifact, cancellation: Cancellation) -> bool:
        target = self.path(artifact.relative_path)
        return target.is_file() and self._matches(target, artifact, cancellation)

    def available(self, artifact: Artifact) -> bool:
        target = self.path(artifact.relative_path)
        return target.is_file() and (artifact.size is None or target.stat().st_size == artifact.size)

    def merge_directory(self, source: str, destination: str, cancellation: Cancellation) -> None:
        origin = self.path(source)
        target = self.path(destination)
        if not origin.is_dir():
            return
        if origin == target or origin.is_relative_to(target) or target.is_relative_to(origin):
            raise CoreError(diagnostic('storage.directory.migration.paths.must.be.independent'))
        target.parent.mkdir(parents=True, exist_ok=True)
        cancellation.check()
        if not target.exists():
            origin.rename(target)
            return
        directories = []
        for entry in origin.rglob("*"):
            cancellation.check()
            if entry.is_symlink():
                continue
            relative = entry.relative_to(origin).as_posix()
            checked = self.path(source + "/" + relative)
            if checked.is_dir():
                directories.append(checked)
            elif checked.is_file():
                output = self.path(destination + "/" + relative)
                if not output.exists():
                    output.parent.mkdir(parents=True, exist_ok=True)
                    checked.rename(output)
        for directory in sorted((*directories, origin), key=lambda path: len(path.parts), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()

    def read(self, relative_path: str, maximum_bytes: int | None = None) -> bytes:
        limit = maximum_bytes or self._config.maximum_metadata_bytes
        with self.path(relative_path).open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise CoreError(diagnostic('storage.file.exceeds.metadata.size.limit'))
        return data

    def read_tail(self, relative_path: str, maximum_bytes: int) -> bytes:
        if type(maximum_bytes) is not int or maximum_bytes < 1:
            raise CoreError(diagnostic('storage.tail.size.must.be.a.positive'))
        with self.path(relative_path).open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - maximum_bytes))
            return stream.read(maximum_bytes)

    def json(self, relative_path: str) -> object:
        return json.loads(self.read(relative_path))

    def begin(self, relative_path: str) -> str:
        target = self.path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".part", dir=target.parent)
        token = uuid4().hex
        with self._lock:
            self._stages[token] = (Path(temporary_name), target, os.fdopen(descriptor, "wb"))
        return token

    def append(self, token: str, data: bytes) -> None:
        with self._lock:
            stream = self._stages[token][2]
        stream.write(data)

    def discard(self, token: str) -> None:
        with self._lock:
            stage = self._stages.pop(token, None)
        if stage:
            temporary, _, stream = stage
            stream.close()
            temporary.unlink(missing_ok=True)

    def commit(self, token: str, artifact: Artifact, cancellation: Cancellation, *, durable: bool = True) -> None:
        with self._lock:
            temporary, target, stream = self._stages[token]
        stream.flush()
        if durable:
            os.fsync(stream.fileno())
        stream.close()
        if not self._matches(temporary, artifact, cancellation):
            raise CoreError(diagnostic('storage.downloaded.file.failed.integrity.verification'))
        cancellation.check()
        self.path(artifact.relative_path)
        os.replace(temporary, target)
        with self._lock:
            self._stages.pop(token)

    def cached(self, artifact: Artifact, cancellation: Cancellation) -> bool:
        path = self.path(artifact.relative_path)
        return bool(artifact.digests) and path.is_file() and self._matches(path, artifact, cancellation)

    def _matches(self, path: Path, artifact: Artifact, cancellation: Cancellation) -> bool:
        if artifact.size is not None and path.stat().st_size != artifact.size:
            return False
        hashes = [(hashlib.new(digest.algorithm), digest.value.lower()) for digest in artifact.digests]
        if hashes:
            with path.open("rb") as stream:
                while chunk := stream.read(self._config.chunk_bytes):
                    cancellation.check()
                    for digest, _ in hashes:
                        digest.update(chunk)
        return all(hmac.compare_digest(digest.hexdigest(), expected) for digest, expected in hashes)

    def write_json(self, relative_path: str, value: object) -> None:
        data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        self.write_bytes(relative_path, data, Cancellation())

    def write_bytes(self, relative_path: str, data: bytes, cancellation: Cancellation) -> None:
        artifact = Artifact("", relative_path, len(data))
        token = self.begin(relative_path)
        try:
            self.append(token, data)
            self.commit(token, artifact, cancellation)
        finally:
            self.discard(token)

    def archive_member(self, relative_path: str, member_name: str, maximum_bytes: int) -> bytes:
        checked_relative(member_name)
        if self.size(relative_path) > self._config.installer_archive_bytes:
            raise CoreError(diagnostic('storage.installer.archive.exceeds.size.limit'))
        with zipfile.ZipFile(self.path(relative_path)) as archive:
            if len(archive.infolist()) > self._config.installer_archive_entries:
                raise CoreError(diagnostic('storage.installer.archive.exceeds.entry.limit'))
            matches = tuple(item for item in archive.infolist() if item.filename == member_name)
            if len(matches) != 1 or matches[0].is_dir() or matches[0].file_size > maximum_bytes or stat.S_ISLNK(matches[0].external_attr >> 16):
                raise CoreError(diagnostic('storage.invalid.or.oversized.installer.archive.member'))
            with archive.open(matches[0]) as stream:
                data = stream.read(maximum_bytes + 1)
            if len(data) > maximum_bytes:
                raise CoreError(diagnostic('storage.installer.archive.member.exceeds.size.limit'))
            return data

    def copy_file(self, source: str, artifact: Artifact, cancellation: Cancellation) -> None:
        token = self.begin(artifact.relative_path)
        try:
            with self.path(source).open("rb") as stream:
                while chunk := stream.read(self._config.chunk_bytes):
                    cancellation.check()
                    self.append(token, chunk)
            self.commit(token, artifact, cancellation)
        finally:
            self.discard(token)

    def fingerprint(self, relative_path: str, cancellation: Cancellation) -> Artifact:
        digest = hashlib.sha256()
        size = 0
        with self.path(relative_path).open("rb") as stream:
            while chunk := stream.read(self._config.chunk_bytes):
                cancellation.check()
                size += len(chunk)
                digest.update(chunk)
        if size == 0:
            raise CoreError(diagnostic('storage.generated.installer.output.is.empty'))
        return Artifact("", relative_path, size, (Digest("sha256", digest.hexdigest()),))

    def extract_natives(self, archives: tuple[NativeArchive, ...], destination: str, cancellation: Cancellation) -> Path:
        target = self.path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise CoreError(diagnostic('storage.native.destination.already.exists'))
        stage = Path(tempfile.mkdtemp(prefix=".natives-", dir=target.parent))
        total = 0
        try:
            for archive_spec in archives:
                with zipfile.ZipFile(self.path(archive_spec.relative_path)) as archive:
                    for member in archive.infolist():
                        cancellation.check()
                        if member.is_dir() or member.filename.startswith("META-INF/") or any(member.filename.startswith(prefix) for prefix in archive_spec.excludes):
                            continue
                        relative = checked_relative(member.filename)
                        if stat.S_ISLNK(member.external_attr >> 16):
                            raise CoreError(diagnostic('storage.native.zip.symlinks.are.unsupported'))
                        total += member.file_size
                        if total > self._config.maximum_native_bytes:
                            raise CoreError(diagnostic('storage.native.zip.exceeds.extraction.limit'))
                        output = stage.joinpath(*relative.parts)
                        output.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member) as source, output.open("wb") as sink:
                            copied = 0
                            while chunk := source.read(self._config.chunk_bytes):
                                cancellation.check()
                                copied += len(chunk)
                                if copied > member.file_size:
                                    raise CoreError(diagnostic('storage.native.zip.size.mismatch'))
                                sink.write(chunk)
            cancellation.check()
            os.replace(stage, target)
            return target
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def remove_directory(self, relative_path: str) -> None:
        target = self.path(relative_path)
        if target.exists():
            shutil.rmtree(target)

    def close(self) -> None:
        with self._lock:
            tokens = tuple(self._stages)
        for token in tokens:
            self.discard(token)
