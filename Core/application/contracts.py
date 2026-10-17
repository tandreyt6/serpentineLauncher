from Core.application.diagnostics import diagnostic
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from math import isfinite

from Core.content.artifact_contracts import Artifact, Digest
from Core.content.mods.mod_contracts import ModJarMetadata
from Core.content.mrpack_contracts import MrpackMetadata
from Core.application.application_contracts import ApplicationSnapshot, BackendResult, CatalogueState, CoreBrowseResult, EditorSnapshot, ModSearchResult, ModProjectResult, ModIconResult, ModFiltersResult, VersionCatalogue, ModQueuePrompt, ModQueueDismissed


@dataclass(frozen=True)
class DownloadBatch:
    artifacts: tuple[Artifact, ...]
    title: str = "Download"
    item_keys: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class DownloadItemProgress:
    task_id: str
    key: str
    completed_bytes: int
    total_bytes: int | None
    verified: bool = False


@dataclass(frozen=True)
class TaskStage:
    key: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key or type(self.weight) not in (int, float) or not isfinite(self.weight) or self.weight <= 0:
            raise ValueError(diagnostic('contracts.invalid.task.stage'))


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    title: str
    state: Literal["queued", "running", "retrying", "paused", "cancelling", "completed", "cancelled", "failed"]
    completed_bytes: int = 0
    total_bytes: int | None = None
    error: str = ""
    stages: tuple[TaskStage, ...] = ()
    stage_index: int = -1
    stage_step: int = 0
    stage_steps: int = 1
    progress: float | None = None
    stage_progress: float | None = None
    bytes_per_second: float = 0.0
    can_retry: bool = False
    retry_count: int = 0
    retry_limit: int = 0


@dataclass(frozen=True)
class ClientSnapshot:
    build_id: str
    state: Literal["starting", "running", "closing", "exited", "failed"]
    pid: int | None = None
    exit_code: int | None = None
    error: str = ""
    launch_origin: Literal["launcher", "editor", "cli"] = "launcher"


@dataclass(frozen=True)
class InstalledCore:
    core_id: str
    minecraft_version: str
    loader: str
    loader_version: str
    profile_path: str


@dataclass(frozen=True)
class CoreInstallation:
    core_id: str
    minecraft_version: str
    loader: str
    loader_version: str
    task_id: str


@dataclass(frozen=True)
class CoreEvent:
    topic: str
    payload: TaskSnapshot | ClientSnapshot | InstalledCore | CoreInstallation | ModJarMetadata | MrpackMetadata | ApplicationSnapshot | BackendResult | CoreBrowseResult | EditorSnapshot | ModSearchResult | ModProjectResult | ModIconResult | ModFiltersResult | VersionCatalogue | CatalogueState | ModQueuePrompt | ModQueueDismissed | DownloadItemProgress


@dataclass(frozen=True)
class PlatformSpec:
    os_name: str
    architecture: str
    os_version: str
    bits: str
    features: tuple[tuple[str, bool], ...] = ()


@dataclass(frozen=True)
class Rule:
    action: Literal["allow", "disallow"]
    os_name: str = ""
    architecture: str = ""
    os_version: str = ""
    features: tuple[tuple[str, bool], ...] = ()


@dataclass(frozen=True)
class Argument:
    values: tuple[str, ...]
    rules: tuple[Rule, ...] | None = None


@dataclass(frozen=True)
class Library:
    name: str
    artifact: Artifact | None
    natives: tuple[tuple[str, Artifact], ...] = ()
    classifiers: tuple[tuple[str, str], ...] = ()
    rules: tuple[Rule, ...] | None = None
    excludes: tuple[str, ...] = ("META-INF/",)


@dataclass(frozen=True)
class AssetIndex:
    index_id: str
    artifact: Artifact


@dataclass(frozen=True)
class LoggingSpec:
    argument: str
    artifact: Artifact


@dataclass(frozen=True)
class VersionProfile:
    version_id: str
    main_class: str
    version_type: str
    client: Artifact | None
    libraries: tuple[Library, ...]
    jvm_arguments: tuple[Argument, ...]
    game_arguments: tuple[Argument, ...]
    asset_index: AssetIndex | None = None
    java_major: int | None = None
    parent_id: str = ""
    client_version: str = ""
    logging: LoggingSpec | None = None


@dataclass(frozen=True)
class VersionEntry:
    version_id: str
    version_type: str
    release_time: str
    artifact: Artifact


@dataclass(frozen=True)
class AccountSession:
    username: str
    uuid: str
    access_token: str = field(repr=False)
    user_type: str = "legacy"
    xuid: str = ""
    client_id: str = ""


@dataclass(frozen=True)
class JavaSettings:
    executable: Path
    minimum_memory_mb: int = 512
    maximum_memory_mb: int = 2048
    extra_arguments: tuple[str, ...] = ()


@dataclass(frozen=True)
class JavaOverrides:
    executable: Path | None = None
    minimum_memory_mb: int | None = None
    maximum_memory_mb: int | None = None
    extra_arguments: tuple[str, ...] | None = None


@dataclass(frozen=True)
class LaunchRequest:
    build_id: str
    core_id: str
    account: AccountSession
    java: JavaSettings
    overrides: JavaOverrides = JavaOverrides()
    width: int | None = None
    height: int | None = None
    fullscreen: bool = False
    launch_origin: Literal["launcher", "editor", "cli"] = "launcher"


@dataclass(frozen=True)
class InstallRequest:
    minecraft_version: str
    loader: Literal["Vanilla", "Fabric", "Quilt", "Forge", "NeoForge"] = "Vanilla"
    loader_version: str = ""
    java_executable: Path | None = None


@dataclass(frozen=True)
class HttpRequest:
    url: str
    offset: int = 0


@dataclass(frozen=True)
class HttpChunk:
    data: bytes


@dataclass(frozen=True)
class LaunchPlan:
    argv: tuple[str, ...] = field(repr=False)
    build_id: str
    working_directory: Path
    log_path: Path


class CoreError(RuntimeError):
    pass


class Cancelled(CoreError):
    pass


class UnsupportedInstaller(CoreError):
    pass
