from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MrpackScanRequest:
    relative_path: str


@dataclass(frozen=True)
class MrpackDiagnostic:
    severity: Literal["warning", "error"]
    code: str
    source: str
    message: str


@dataclass(frozen=True)
class MrpackDependency:
    dependency_id: str
    version: str
    known: bool


@dataclass(frozen=True)
class MrpackHash:
    algorithm: str
    value: str


@dataclass(frozen=True)
class MrpackFile:
    path: str
    hashes: tuple[MrpackHash, ...]
    downloads: tuple[str, ...]
    file_size: int
    client: str | None
    server: str | None
    environment_declared: bool
    valid: bool
    custom_metadata_json: str = "{}"
    raw_metadata_json: str = "{}"


@dataclass(frozen=True)
class MrpackOverride:
    archive_path: str
    destination_path: str
    scope: Literal["shared", "client", "server"]
    file_size: int
    compressed_size: int
    crc32: int
    compression_method: int


@dataclass(frozen=True)
class MrpackMetadata:
    relative_path: str
    sha256: str
    archive_bytes: int
    archive_entries: int
    format_version: int
    game: str
    version_id: str
    name: str
    summary: str | None
    dependencies: tuple[MrpackDependency, ...]
    files: tuple[MrpackFile, ...]
    overrides: tuple[MrpackOverride, ...]
    other_entries: tuple[str, ...]
    diagnostics: tuple[MrpackDiagnostic, ...]
    valid: bool
    custom_metadata_json: str = "{}"
