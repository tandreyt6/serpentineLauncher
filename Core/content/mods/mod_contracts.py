from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ModScanRequest:
    relative_path: str
    include_nested: bool = True


@dataclass(frozen=True)
class ModDiagnostic:
    code: str
    message: str
    source: str
    archive_chain: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModPerson:
    name: str
    roles: tuple[str, ...] = ()
    contacts: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ModLicense:
    identifier: str
    name: str = ""
    url: str = ""
    description: str = ""


@dataclass(frozen=True)
class ModDependency:
    mod_id: str
    kind: str
    version_expression: str
    syntax: Literal["fabric", "quilt", "maven", "legacy"]
    side: str = ""
    ordering: str = ""
    reason: str = ""
    raw_expression: str = ""


@dataclass(frozen=True)
class ModIconReference:
    member_path: str
    declared_size: int | None = None


@dataclass(frozen=True)
class ModRecord:
    record_key: str
    mod_id: str
    name: str
    version: str
    raw_version: str
    description: str
    loaders: tuple[str, ...]
    metadata_format: str
    source: str
    archive_chain: tuple[str, ...]
    authors: tuple[ModPerson, ...] = ()
    contributors: tuple[ModPerson, ...] = ()
    authors_text: str = ""
    licenses: tuple[ModLicense, ...] = ()
    contacts: tuple[tuple[str, str], ...] = ()
    dependencies: tuple[ModDependency, ...] = ()
    icons: tuple[ModIconReference, ...] = ()
    environment: str = "unknown"
    language_loader: str = ""
    language_loader_range: str = ""
    provided_ids: tuple[str, ...] = ()
    credits: str = ""
    custom_metadata_json: str = ""



@dataclass(frozen=True)
class ModDescriptor:
    source: str
    metadata_format: str
    loaders: tuple[str, ...]
    archive_chain: tuple[str, ...]
    record_keys: tuple[str, ...]
    schema_version: int | None = None
    custom_metadata_json: str = ""
    parse_status: Literal["parsed", "invalid"] = "parsed"


@dataclass(frozen=True)
class ModIconAsset:
    member_path: str
    archive_chain: tuple[str, ...]
    width: int
    height: int
    sha256: str
    png_bytes: bytes


@dataclass(frozen=True)
class ModJarMetadata:
    relative_path: str
    sha256: str
    descriptors: tuple[ModDescriptor, ...]
    mods: tuple[ModRecord, ...]
    icons: tuple[ModIconAsset, ...]
    diagnostics: tuple[ModDiagnostic, ...]


@dataclass(frozen=True)
class CachedModIcon:
    relative_path: str
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class ParsedModDescriptor:
    descriptor: ModDescriptor
    mods: tuple[ModRecord, ...]
    nested_paths: tuple[str, ...]
    diagnostics: tuple[ModDiagnostic, ...]
