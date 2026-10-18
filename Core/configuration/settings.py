from pathlib import Path
import json
from Core.resources.runtime import resource_root


ROOT = Path(__file__).resolve().parents[2]
APP_NAME = "Serpantine Launcher"
APP_VERSION = "V5.1.1-beta.1"
UPDATE_API_URL = 'https://api.github.com/repos/tandreyt6/serpentineLauncher/releases/latest'
UI_DIRECTORY = resource_root("ui", ROOT / "ui")
ASSETS_DIRECTORY = resource_root("assets", ROOT / "assets")
UI_STYLE_DEFAULTS = json.loads((ASSETS_DIRECTORY / "ui-defaults.json").read_text(encoding="utf-8"))
APP_ICON = ASSETS_DIRECTORY / "icon.ico"
APP_ID = "Serpantine.Launcher.V5"
ICON_CANVAS_PIXELS = 64
ICON_DRAWING_PIXELS = 48
ICON_MINIMUM_ALPHA = 8
ICON_MINIMUM_COMPONENT_SPAN = 3
THEMES_DIRECTORY = ROOT / "themes"
LANGUAGES_DIRECTORY = ROOT / "langs"
BUILDS_DIRECTORY = ROOT / "builds"
CORES_DIRECTORY = ROOT / "Cores"
LIBS_DIRECTORY = ROOT / "libs"
CORE_RESOURCES_METADATA_FILENAME = "SerpantineResources.json"
LOGS_DIRECTORY = ROOT / "logs"
BUILD_METADATA_FILENAME = "SerpantineBuild.json"
DEFAULT_THEME = "serpantine-night"
THEME_UPDATE_SUFFIX = ".pending"
DEFAULT_LOCALE = "ru"
MINIMUM_MEMORY_MB = 512
DEFAULT_JAVA_MEMORY_PERCENT = 60
PREVIEW_MEMORY_LIMIT_MB = 16384
INITIAL_WINDOW_WIDTH = 1120
INITIAL_WINDOW_HEIGHT = 740
MINIMUM_WINDOW_WIDTH = 940
MINIMUM_WINDOW_HEIGHT = 660
CORE_DOWNLOAD_WORKERS = 32
CORE_TASK_WORKERS = 3
CORE_FILE_TASK_WORKERS = 2
CORE_NETWORK_TIMEOUT_SECONDS = 30.0
CORE_NETWORK_CONNECT_TIMEOUT_SECONDS = 8.0
CORE_NETWORK_CONNECT_WORKERS = 8
CORE_NETWORK_READ_TIMEOUT_SECONDS = 10.0
CORE_NETWORK_ADDRESS_DELAY_SECONDS = 0.25
CORE_NETWORK_DNS_CACHE_SECONDS = 60.0
CORE_DOWNLOAD_RETRIES = 3
CORE_DOWNLOAD_CHUNK_BYTES = 262144
CORE_USER_AGENT = f"{APP_NAME}/{APP_VERSION}"
CORE_VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
CORE_ASSET_CDN = "https://resources.download.minecraft.net"
CORE_LIBRARY_CDN = "https://libraries.minecraft.net"
CORE_FABRIC_META_URL = "https://meta.fabricmc.net/v2"
CORE_QUILT_META_URL = "https://meta.quiltmc.org/v3"
CORE_FORGE_MAVEN_URL = "https://maven.minecraftforge.net"
CORE_NEOFORGE_MAVEN_URL = "https://maven.neoforged.net/releases"
CORE_INSTALLER_DIRECTORY = "installers"
CORE_INSTALLER_WORK_DIRECTORY = "installer-work"
CORE_INSTALLER_LOGS_DIRECTORY = "installers"
CORE_INSTALLER_PROCESS_TIMEOUT_SECONDS = 600.0
CORE_INSTALLER_ARCHIVE_BYTES = 134217728
CORE_INSTALLER_ARCHIVE_ENTRIES = 20000
CORE_CACHE_DIRECTORY = "cache"
CORE_INSTALL_METADATA_FILENAME = "SerpantineCore.json"
CORE_PROFILE_FILENAME = "profile.json"
CORE_INTEGRITY_FILENAME = "integrity.json"
CORE_BUILD_RUNTIME_DIRECTORY = ".serpantine"
CORE_NATIVES_DIRECTORY = "natives"
CORE_BUILD_LOGS_DIRECTORY = "logs"
CORE_JAVA_PROBES_DIRECTORY = "java-probes"
CORE_MAXIMUM_METADATA_BYTES = 33554432
CORE_MAXIMUM_NATIVE_BYTES = 536870912
CORE_PROFILE_DEPTH_LIMIT = 8
CORE_RETRY_DELAY_SECONDS = 0.25
CORE_JAVA_PROBE_TIMEOUT_SECONDS = 10.0
CORE_JAVA_DISCOVERY_WORKERS = 4
CORE_CLIENT_SHUTDOWN_TIMEOUT_SECONDS = 10.0
CORE_PROCESS_WAIT_INTERVAL_SECONDS = 0.05
CORE_PROCESS_JOB_SNAPSHOT_ATTEMPTS = 8
CORE_CONTROL_WAIT_INTERVAL_SECONDS = 0.05
CORE_MOD_JAR_BYTES = 134217728
COLLECTION_IMPORT_FILE_BYTES = 1073741824
COLLECTION_IMPORT_TOTAL_BYTES = 8589934592
CONFIG_FILE_EXTENSIONS = (".json", ".json5", ".toml", ".yaml", ".yml", ".properties", ".cfg", ".ini", ".conf", ".txt", ".xml", ".hocon")
CORE_MOD_METADATA_BYTES = 1048576
CORE_MOD_ARCHIVE_ENTRIES = 10000
CORE_MOD_SCAN_ENTRIES = 20000
CORE_MOD_SCAN_BYTES = 67108864
CORE_MOD_NESTED_JAR_BYTES = 33554432
CORE_MOD_NESTED_DEPTH = 4
CORE_MOD_RECORDS = 1024
CORE_MOD_COMPRESSION_RATIO = 1000
CORE_MOD_ICON_BYTES = 4194304
CORE_MOD_ICON_DIMENSION = 4096
CORE_MOD_ICON_PIXELS = 4194304
CORE_MOD_ICON_DECODED_BYTES = 33554432
CORE_MOD_CACHE_ENTRIES = 16
CORE_MOD_CACHE_BYTES = 33554432
CORE_MOD_ICON_CACHE_DIRECTORY = "mod-icons"
CORE_MRPACK_ARCHIVE_BYTES = 268435456
CORE_MRPACK_INDEX_BYTES = 4194304
CORE_MRPACK_ARCHIVE_ENTRIES = 20000
CORE_MRPACK_FILES = 10000
CORE_MRPACK_OVERRIDE_BYTES = 268435456
CORE_MRPACK_OVERRIDES_BYTES = 1073741824
CORE_MRPACK_DOWNLOAD_FILE_BYTES = 4294967296
CORE_MRPACK_URLS_PER_FILE = 16
CORE_MRPACK_COMPRESSION_RATIO = 1000
CORE_MRPACK_CACHE_ENTRIES = 8
CORE_MRPACK_CACHE_BYTES = 16777216
CORE_MRPACK_ALLOWED_DOWNLOAD_HOSTS = ("cdn.modrinth.com", "github.com", "raw.githubusercontent.com", "gitlab.com")
APPLICATION_STATE_FILENAME = "SerpantineLauncher.json"
APPLICATION_CATALOG_FILENAME = "catalog.json"
CORE_CATALOGUE_PAGE_SIZE = 80
CORE_BROWSER_FILTER_CACHE_ENTRIES = 8
CORE_BROWSER_FILTER_CACHE_ROWS = 320
BACKEND_EVENT_INTERVAL_MS = 80
BACKEND_BUSY_EVENT_INTERVAL_MS = 16
STARTUP_POLL_INTERVAL_MS = 8
STARTUP_INCUBATION_INTERVAL_MS = 1
STARTUP_VISUAL_BUDGET_MS = 4
STARTUP_ACTIVATION_INTERVAL_MS = 100
THEME_SETTLE_INTERVAL_MS = 1000
DESCRIPTION_CACHE_BYTES = 2097152
DESCRIPTION_CACHE_ENTRIES = 64
MOD_CATALOGUE_PAGE_SIZE = 30
MOD_SEARCH_QUERY_LENGTH = 256
MOD_CATALOGUE_MAXIMUM_PAGE_SIZE = 100
MOD_DESCRIPTION_LENGTH = 2000
MOD_AUTHOR_LENGTH = 200
MODRINTH_PROJECT_HOSTS = ("modrinth.com", "www.modrinth.com")
MODRINTH_DOWNLOAD_HOST = "cdn.modrinth.com"
BACKEND_EVENT_DRAIN_LIMIT = 1000
BACKEND_EVENT_DRAIN_BUDGET_MS = 4
DEFAULT_GAME_WINDOW_WIDTH = 1280
DEFAULT_GAME_WINDOW_HEIGHT = 720
MINIMUM_GAME_WINDOW_WIDTH = 320
MINIMUM_GAME_WINDOW_HEIGHT = 240
MAXIMUM_GAME_WINDOW_DIMENSION = 16384
DEFAULT_BUILD_TITLE_COLOR = UI_STYLE_DEFAULTS["buildTitleColor"]
BUILTIN_LOCALE = "en"
IPC_DIRECTORY_NAME = "SerpantineLauncher"
IPC_MAXIMUM_BYTES = 1048576
IPC_READY_TIMEOUT_SECONDS = 30.0
IPC_RESPONSE_TIMEOUT_SECONDS = 1800.0
IPC_POLL_INTERVAL_SECONDS = 0.05
IPC_WORKERS = 4
MODRINTH_API_URL = "https://api.modrinth.com/v2"
MODRINTH_PROJECT_URL = "https://modrinth.com"
THEME_SCENE_BYTES = 134217728
THEME_PACKAGE_BYTES = 268435456
THEME_HEALTH_FILENAME = "SerpantineThemeHealth.json"
THEME_HEALTH_BYTES = 1048576
THEME_FAILURE_DETAIL_LENGTH = 8192
MEBIBYTE_BYTES = 1048576
FORGE_CATALOG_URL = "https://files.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json"
NEOFORGE_CATALOG_URL = "https://meta.prismlauncher.org/v1/net.neoforged/index.json"
SHORTCUT_ACTIONS = (
    ("quickSwitch", "Ctrl+K", ("main", "editor")),
    ("createBuild", "Ctrl+N", ("main",)),
    ("launchBuild", "F6", ("main", "editor")),
    ("stopBuild", "Shift+F6", ("main", "editor")),
    ("editBuild", "Ctrl+E", ("main",)),
    ("openFolder", "Ctrl+Shift+O", ("main", "editor")),
    ("tasks", "Ctrl+J", ("main", "editor")),
    ("settings", "Ctrl+,", ("main",)),
    ("find", "Ctrl+F", ("main", "editor")),
    ("refresh", "F5", ("main", "editor")),
    ("back", "Alt+Left", ("main", "editor")),
    ("save", "Ctrl+S", ("editor",)),
    ("saveAll", "Ctrl+Shift+S", ("editor",)),
    ("closeTab", "Ctrl+W", ("editor",)),
    ("nextTab", "Ctrl+Tab", ("editor",)),
    ("previousTab", "Ctrl+Shift+Tab", ("editor",)),
    ("quickLaunch", "Ctrl+Return", ("palette",)),
)
SHORTCUT_RESERVED = (
    "Ctrl+A", "Ctrl+C", "Ctrl+X", "Ctrl+V", "Ctrl+Z", "Ctrl+Y", "Ctrl+Shift+Z", "Ctrl+Shift+V", "Ctrl+Ins",
    "Ctrl+Left", "Ctrl+Right", "Ctrl+Home", "Ctrl+End", "Ctrl+Shift+Left", "Ctrl+Shift+Right", "Ctrl+Shift+Home", "Ctrl+Shift+End",
    "Ctrl+Backspace", "Ctrl+Del", "Ctrl+Shift+Backspace", "Ctrl+Shift+Del",
    "Alt+F4", "Alt+Tab", "Alt+Shift+Tab", "Alt+Space", "Ctrl+Esc", "Ctrl+Alt+Del", "Ctrl+Shift+Esc",
)
MINECRAFT_VERSION_FILTERS = (
    ("release", "minecraftShowReleases", "minecraft.version_type.release"),
    ("snapshot", "minecraftShowSnapshots", "minecraft.version_type.snapshot"),
    ("old_beta", "minecraftShowBeta", "minecraft.version_type.old_beta"),
    ("old_alpha", "minecraftShowAlpha", "minecraft.version_type.old_alpha"),
)

APPLICATION_SETTINGS = {
    **{setting: True for category, setting, text_key in MINECRAFT_VERSION_FILTERS},
    **{"shortcut." + key: sequence for key, sequence, scopes in SHORTCUT_ACTIONS},
    "hardwareAcceleration": True,
    "panelSide": "left", "panelMode": "hover", "panelLayout": "overlay", "panelAlign": "center", "panelLabels": "text",
    "buildView": "cards", "buildCardSize": "small", "coreView": "cards", "safeMode": True,
    "buildDoubleClickAction": "play",
    "javaPath": "", "javaVersion": "auto", "memoryMin": "512", "memoryMax": "2048", "jvmArgs": "",
    "firstRunComplete": False,
    "silentUpdates": True,
    "delaySystemShutdown": False,
    "javaRestrictions": "default", "closeAction": "tray", "launchAction": "nothing", "finishAction": "last",
    "modDrop": True, "logMode": "normal", "zipBatch": "5", "reducedMotion": False, "theme": DEFAULT_THEME, "locale": DEFAULT_LOCALE,
    "editorWrap": False, "editorLineNumbers": True, "editorHighlighting": True,
    "logWrap": False, "logFollowTail": True,
    "editorDefaultSection": "general", "editorShowDetachButton": True, "editorDetachDistance": "50",
    "panelAnimationMs": "90", "panelHoverCloseMs": "300", "tooltipDelayMs": "400", "notificationDurationMs": "3500",
    "notificationPolicy": "drop-oldest", "tasksAutoOpen": False, "tasksDisplay": "active",
    "downloadRetries": str(CORE_DOWNLOAD_RETRIES),
}

INTERACTION_TIMING_SETTINGS = ("panelAnimationMs", "panelHoverCloseMs", "tooltipDelayMs")
MAXIMUM_UI_TIMING_MS = 3000

APPLICATION_SETTING_RANGES = {
    "downloadRetries": (0, 5),
    **dict.fromkeys(INTERACTION_TIMING_SETTINGS, (0, MAXIMUM_UI_TIMING_MS)),
    "notificationDurationMs": (500, 30000), "editorDetachDistance": (5, 300),
}

APPLICATION_SETTING_CHOICES = {
    "panelSide": ("left", "right", "top", "bottom"),
    "panelLabels": ("icons", "text"),
    "buildCardSize": ("tiny", "small", "medium", "large", "huge"),
    "buildDoubleClickAction": ("play", "edit", "about", "nothing"),
    "editorDefaultSection": ("general", "java", "mods", "packs", "shaders", "configs", "files", "logs", "worlds"),
    "notificationPolicy": ("drop-oldest", "reject-new", "replace-current"),
    "tasksDisplay": ("active", "latest"),
}

UI_RUNTIME_SETTINGS = (
    ("reducedMotion", "motion.reduced", bool),
    ("panelAnimationMs", "navigation.duration_ms", int),
    ("tooltipDelayMs", "ui.tooltip_delay_ms", int),
    ("notificationDurationMs", "notifications.lifetime_ms", int),
    ("notificationPolicy", "notifications.policy", str),
    ("editorDetachDistance", "workspace.detach_distance", int),
)

CORE_APPEARANCE_INDEX_BYTES = 4194304

CORE_APPEARANCE_ENTRY_BYTES = 67108864

CORE_APPEARANCE_PACK_ENTRIES = 10000

CORE_CORES_DIRECTORY = "Cores"

CORE_LIBS_DIRECTORY = "libs"

CORE_BUILDS_DIRECTORY = "builds"

CORE_LOGS_DIRECTORY = "logs"

CORE_DOWNLOAD_ITEM_INTERVAL = 0.08
CORE_DOWNLOAD_PROGRESS_INTERVAL = 0.1
CORE_DOWNLOAD_SPEED_WINDOW_SECONDS = 1.0
CORE_HTTP_REDIRECT_LIMIT = 10
EDITOR_FILE_CHANGE_DELAY_MS = 250
