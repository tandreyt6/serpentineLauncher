from Core.application.diagnostics import diagnostic
from dataclasses import dataclass
from Core.configuration.settings import DEFAULT_BUILD_TITLE_COLOR, CORE_CATALOGUE_PAGE_SIZE, MOD_CATALOGUE_PAGE_SIZE
from pathlib import Path
from typing import Literal

from Core.content.artifact_contracts import Artifact


@dataclass(frozen=True)
class BuildRecord:
    id: str
    title: str
    minecraft: str
    loader: str
    loader_version: str = ""
    description: str = ""
    description_format: str = "md"
    background: str = ""
    java_path: str = ""
    memory_min: int | None = None
    memory_max: int | None = None
    jvm_args: str = ""
    width: int | None = None
    height: int | None = None
    fullscreen: bool = False
    title_color: str = DEFAULT_BUILD_TITLE_COLOR


@dataclass(frozen=True)
class AccountRecord:
    id: str
    name: str
    uuid: str


@dataclass(frozen=True)
class ModQueueRecord:
    id: str
    title: str
    source: str
    owner_id: str
    state: Literal["queued", "downloading"] = "queued"
    method: Literal["download", "copy"] = "download"
    version_id: str = ""
    copy_source: str = ""
    version_number: str = ""
    queue_id: str = ""
    artifact: Artifact | None = None
    required_by: tuple[str, ...] = ()
    replacements: tuple[tuple[str, str], ...] = ()
    minecraft: tuple[str, ...] = ()
    loaders: tuple[str, ...] = ()
    content_kind: str = 'mod'
    required_project_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedMod:
    project_id: str
    version_id: str
    title: str
    number: str
    artifact: Artifact
    required_by: tuple[str, ...] = ()
    exact: bool = True
    minecraft: tuple[str, ...] = ()
    loaders: tuple[str, ...] = ()
    content_kind: str = 'mod'
    required_project_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LocalMod:
    path: str
    sha512: str
    sha1: str
    project_id: str = ""
    version_id: str = ""
    number: str = ""
    minecraft: tuple[str, ...] = ()
    loaders: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModConflict:
    title: str
    required_by: tuple[str, ...]
    required: str
    current: tuple[str, ...]
    disabled: bool = False


@dataclass(frozen=True, slots=True)
class ModQueuePrompt:
    build_id: str
    request_id: str
    kind: str
    title: str
    conflicts: tuple[ModConflict, ...] = ()
    window_key: str = ""
    filename: str = ""
    version: str = ""
    current_versions: tuple[str, ...] = ()
    files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModQueueDismissed:
    build_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class ModAddPlan:
    request_id: str
    build: BuildRecord
    items: tuple[ResolvedMod, ...]
    queue: tuple[ModQueueRecord, ...]
    installed: tuple[LocalMod, ...]
    duplicate: str = ""
    dependencies: str = ""
    window_key: str = ""


@dataclass(frozen=True, slots=True)
class CoreChoice:
    id: str
    minecraft: str
    loader: str
    version: str
    installed: bool = False


@dataclass(frozen=True, slots=True)
class VersionCatalogue:
    loader: str
    minecraft: str
    cores: tuple[CoreChoice, ...]
    revision: int = 0


@dataclass(frozen=True, slots=True)
class CatalogueState:
    revision: int
    updating: bool
    minecraft_versions: tuple[str, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CatalogueSource:
    loader: str
    games: tuple[str, ...] = ()
    versions: tuple[str, ...] = ()
    cores: tuple[CoreChoice, ...] = ()


@dataclass(frozen=True, slots=True)
class CoreBrowseRequest:
    request_id: str
    state: str = "all"
    loader: str = ""
    minecraft: str = ""
    offset: int = 0
    limit: int = CORE_CATALOGUE_PAGE_SIZE


@dataclass(frozen=True, slots=True)
class CoreBrowseResult:
    request_id: str
    offset: int
    cores: tuple[CoreChoice, ...]
    more: bool
    errors: tuple[str, ...] = ()
    minecraft_versions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicationSnapshot:
    builds: tuple[BuildRecord, ...]
    accounts: tuple[AccountRecord, ...]
    account: str
    settings: tuple[tuple[str, str | bool], ...]
    queue: tuple[ModQueueRecord, ...]
    cores: tuple[CoreChoice, ...]
    minecraft_versions: tuple[str, ...]
    memory_limit: int


@dataclass(frozen=True)
class ApplicationCommand:
    action: str
    key: str = ""
    value: str = ""
    fields: tuple[tuple[str, str], ...] = ()
    launch_origin: Literal["launcher", "editor", "cli"] = "launcher"

    def __post_init__(self) -> None:
        if self.launch_origin not in ("launcher", "editor", "cli"):
            raise ValueError(diagnostic('application_contracts.unknown.launch.origin'))
        if any(not isinstance(value, str) for value in (self.action, self.key, self.value)):
            raise TypeError(diagnostic('application_contracts.application.command.values.must.be.strings'))
        if not isinstance(self.fields, tuple) or any(not isinstance(pair, tuple) or len(pair) != 2 or any(not isinstance(value, str) for value in pair) for pair in self.fields):
            raise TypeError(diagnostic('application_contracts.application.command.fields.require.immutable.string'))
        if len({name for name, _ in self.fields}) != len(self.fields):
            raise ValueError(diagnostic('application_contracts.application.command.fields.cannot.contain.duplicate'))


@dataclass(frozen=True)
class BackendResult:
    action: str
    key: str = ""
    text: str = ""
    path: str = ""


@dataclass(frozen=True)
class FileEntry:
    path: str
    name: str
    folder: bool
    date: str = ""
    text: str = ""
    config: bool = False
    formatted_text: str = ""


@dataclass(frozen=True)
class ModEntry:
    path: str
    title: str
    version: str
    description: str
    authors: str
    icon: str
    enabled: bool


@dataclass(frozen=True)
class EditorSnapshot:
    build_id: str
    files: tuple[FileEntry, ...]
    logs: tuple[FileEntry, ...]
    mods: tuple[ModEntry, ...]


@dataclass(frozen=True)
class ModSearchResult:
    build_id: str
    mods: tuple["ModCatalogEntry", ...]
    request_id: str = ""
    offset: int = 0
    next_offset: int = 0
    more: bool = False
    content_kind: str = 'mod'


@dataclass(frozen=True, slots=True)
class ModSearchRequest:
    build_id: str
    request_id: str
    query: str = ""
    offset: int = 0
    limit: int = MOD_CATALOGUE_PAGE_SIZE
    category: str = ""
    sort: str = ""
    minecraft: str = ""
    loader: str = ""
    content_kind: str = 'mod'


@dataclass(frozen=True, slots=True)
class ModCatalogEntry:
    id: str
    title: str
    source: str
    owner_id: str
    description: str = ""
    author: str = ""
    downloads: int = 0
    icon_url: str = ""


@dataclass(frozen=True, slots=True)
class ModVersionEntry:
    id: str
    number: str
    name: str
    channel: str
    published: str
    filename: str
    size: int
    minecraft: tuple[str, ...] = ()
    loaders: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModProjectResult:
    build_id: str
    request_id: str
    project_id: str
    title: str
    description: str
    body: str
    icon_url: str
    versions: tuple[ModVersionEntry, ...]
    content_kind: str = 'mod'


@dataclass(frozen=True, slots=True)
class ModIconResult:
    project_id: str
    path: str


@dataclass(frozen=True, slots=True)
class ModFiltersResult:
    build_id: str
    categories: tuple[str, ...]
    content_kind: str = 'mod'


@dataclass(frozen=True, slots=True)
class ModFileChoice:
    project_id: str
    version_id: str
    artifact: "Artifact"


@dataclass(frozen=True, slots=True)
class ModCopyFailure:
    id: str
    title: str
    reason: str


@dataclass(frozen=True, slots=True)
class ModCopyFailures:
    build_id: str
    failures: tuple[ModCopyFailure, ...]


@dataclass(frozen=True)
class AppearanceScanRequest:
    kind: str
    directories: tuple[Path, ...]
    pending_suffix: str = ""


@dataclass(frozen=True)
class LanguagePack:
    id: str
    entries: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ThemeFile:
    id: str
    path: Path
    icon_key: str = ""


@dataclass(frozen=True)
class AppearanceCatalogue:
    kind: str
    languages: tuple[LanguagePack, ...] = ()
    themes: tuple[ThemeFile, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class VisualResourcesRequest:
    assets: Path
    languages: Path
    themes: Path
    default_theme: str
    pending_suffix: str


@dataclass(frozen=True)
class VisualResources:
    languages: tuple[LanguagePack, ...]
    icons: tuple[tuple[str, Path], ...]
    images: tuple[tuple[str, Path], ...]
    pending_themes: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()
