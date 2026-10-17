from dataclasses import dataclass
from Core.configuration.settings import DEFAULT_BUILD_TITLE_COLOR


@dataclass(frozen=True)
class SettingChoice:
    key: str
    text_key: str


@dataclass(frozen=True)
class CardSizeOption:
    key: str
    text_key: str
    width_token: str


@dataclass(frozen=True)
class PreviewCommand:
    action: str
    key: str = ""
    value: str = ""
    launch_origin: str = "launcher"


@dataclass(frozen=True)
class CreateBuildPreview:
    title: str
    id: str
    minecraft: str
    loader: str
    loader_version: str


@dataclass(frozen=True)
class BuildDecorationPreview:
    id: str
    title: str
    description: str
    background: str
    description_format: str = "md"
    title_color: str | None = None


@dataclass(frozen=True)
class BuildCorePreview:
    installed: bool
    core_id: str = ""
    progress: float = -1
    paused: bool = False
    pending_changes: bool = False
    syncing: bool = False
    stage: str = ""


@dataclass(frozen=True)
class BuildPreview:
    id: str
    title: str
    minecraft: str
    loader: str
    loader_version: str
    description_key: str
    scenery: int
    running: bool = False
    background: str = ""
    description_format: str = "md"
    title_color: str = DEFAULT_BUILD_TITLE_COLOR


@dataclass(frozen=True)
class AccountPreview:
    id: str
    name: str
    initials: str


@dataclass(frozen=True)
class CorePreview:
    id: str
    minecraft: str
    loader: str
    version: str
    installed: bool
    progress: float = -1
    paused: bool = False
    stage: str = ""


@dataclass(frozen=True)
class DownloadPreview:
    id: str
    title: str
    progress: float
    kind: str
    owner_id: str
    paused: bool = False
    stage: str = ""
    stage_progress: int = -1
    bytes_per_second: float = 0.0
    state: str = 'running'
    error: str = ''
    can_retry: bool = False


@dataclass(frozen=True)
class QueuedModPreview:
    id: str
    title: str
    source: str
    owner_id: str
    state: str = "queued"
    version_id: str = ""
    version_number: str = ""


@dataclass(frozen=True)
class DescriptionDocument:
    source: str
    format: str


@dataclass(frozen=True)
class BuildFilter:
    name: str = ""
    id: str = ""
    minecraft: str = ""
    loader: str = ""
    loader_version: str = ""
    state: str = "all"


@dataclass(frozen=True)
class EditorCommand:
    action: str
    key: str = ""
    target: str = ""
    value: str = ""
    index: int = -1
    x: float = 0
    y: float = 0
    content_kind: str = 'mod'


@dataclass(frozen=True)
class EditorSaveState:
    key: str
    available: bool


@dataclass(frozen=True)
class EditorTab:
    key: str
    build_id: str
    kind: str
    path: str = ""
    content_kind: str = 'mod'


@dataclass(frozen=True)
class ConfigPreview:
    path: str
    text: str


@dataclass(frozen=True)
class LogPreview:
    date: str
    name: str
    text: str
