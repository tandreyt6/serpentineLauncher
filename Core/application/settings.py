from Core.application.diagnostics import diagnostic
import Core.configuration.settings as config
from dataclasses import dataclass
from pathlib import Path
from math import isfinite


@dataclass(frozen=True)
class CoreConfig:
    root: Path
    java_discovery_workers: int = config.CORE_JAVA_DISCOVERY_WORKERS
    network_connect_workers: int = config.CORE_NETWORK_CONNECT_WORKERS
    appearance_index_bytes: int = config.CORE_APPEARANCE_INDEX_BYTES
    appearance_entry_bytes: int = config.CORE_APPEARANCE_ENTRY_BYTES
    appearance_pack_entries: int = config.CORE_APPEARANCE_PACK_ENTRIES
    import_file_bytes: int = config.COLLECTION_IMPORT_FILE_BYTES
    import_total_bytes: int = config.COLLECTION_IMPORT_TOTAL_BYTES
    config_file_extensions: tuple[str, ...] = config.CONFIG_FILE_EXTENSIONS
    application_state_filename: str = config.APPLICATION_STATE_FILENAME
    application_catalog_filename: str = config.APPLICATION_CATALOG_FILENAME
    core_catalogue_page_size: int = config.CORE_CATALOGUE_PAGE_SIZE
    application_settings: tuple[tuple[str, str | bool], ...] = ()
    modrinth_api_url: str = config.MODRINTH_API_URL
    forge_catalog_url: str = config.FORGE_CATALOG_URL
    neoforge_catalog_url: str = config.NEOFORGE_CATALOG_URL
    cores_directory: str = config.CORE_CORES_DIRECTORY
    libs_directory: str = config.CORE_LIBS_DIRECTORY
    resources_metadata_filename: str = config.CORE_RESOURCES_METADATA_FILENAME
    builds_directory: str = config.CORE_BUILDS_DIRECTORY
    logs_directory: str = config.CORE_LOGS_DIRECTORY
    build_metadata_filename: str = config.BUILD_METADATA_FILENAME
    cache_directory: str = config.CORE_CACHE_DIRECTORY
    install_metadata_filename: str = config.CORE_INSTALL_METADATA_FILENAME
    profile_filename: str = config.CORE_PROFILE_FILENAME
    integrity_filename: str = config.CORE_INTEGRITY_FILENAME
    build_runtime_directory: str = config.CORE_BUILD_RUNTIME_DIRECTORY
    natives_directory: str = config.CORE_NATIVES_DIRECTORY
    build_logs_directory: str = config.CORE_BUILD_LOGS_DIRECTORY
    java_probes_directory: str = config.CORE_JAVA_PROBES_DIRECTORY
    profile_depth_limit: int = config.CORE_PROFILE_DEPTH_LIMIT
    download_workers: int = config.CORE_DOWNLOAD_WORKERS
    download_item_interval: float = config.CORE_DOWNLOAD_ITEM_INTERVAL
    download_progress_interval: float = config.CORE_DOWNLOAD_PROGRESS_INTERVAL
    download_speed_window: float = config.CORE_DOWNLOAD_SPEED_WINDOW_SECONDS
    task_workers: int = config.CORE_TASK_WORKERS
    network_timeout: float = config.CORE_NETWORK_TIMEOUT_SECONDS
    network_connect_timeout: float = config.CORE_NETWORK_CONNECT_TIMEOUT_SECONDS
    network_read_timeout: float = config.CORE_NETWORK_READ_TIMEOUT_SECONDS
    download_retries: int = config.CORE_DOWNLOAD_RETRIES
    chunk_bytes: int = config.CORE_DOWNLOAD_CHUNK_BYTES
    user_agent: str = config.CORE_USER_AGENT
    manifest_url: str = config.CORE_VERSION_MANIFEST_URL
    asset_cdn: str = config.CORE_ASSET_CDN
    library_cdn: str = config.CORE_LIBRARY_CDN
    fabric_meta_url: str = config.CORE_FABRIC_META_URL
    quilt_meta_url: str = config.CORE_QUILT_META_URL
    forge_maven_url: str = config.CORE_FORGE_MAVEN_URL
    neoforge_maven_url: str = config.CORE_NEOFORGE_MAVEN_URL
    installer_directory: str = config.CORE_INSTALLER_DIRECTORY
    installer_work_directory: str = config.CORE_INSTALLER_WORK_DIRECTORY
    installer_logs_directory: str = config.CORE_INSTALLER_LOGS_DIRECTORY
    installer_process_timeout: float = config.CORE_INSTALLER_PROCESS_TIMEOUT_SECONDS
    installer_archive_bytes: int = config.CORE_INSTALLER_ARCHIVE_BYTES
    installer_archive_entries: int = config.CORE_INSTALLER_ARCHIVE_ENTRIES
    maximum_metadata_bytes: int = config.CORE_MAXIMUM_METADATA_BYTES
    maximum_native_bytes: int = config.CORE_MAXIMUM_NATIVE_BYTES
    retry_delay: float = config.CORE_RETRY_DELAY_SECONDS
    java_probe_timeout: float = config.CORE_JAVA_PROBE_TIMEOUT_SECONDS
    client_shutdown_timeout: float = config.CORE_CLIENT_SHUTDOWN_TIMEOUT_SECONDS
    control_wait_interval: float = config.CORE_CONTROL_WAIT_INTERVAL_SECONDS
    minimum_memory_mb: int = config.MINIMUM_MEMORY_MB
    default_java_memory_percent: int = config.DEFAULT_JAVA_MEMORY_PERCENT
    available_memory_mb: int | None = None
    launcher_name: str = config.APP_NAME
    launcher_version: str = config.APP_VERSION
    mod_jar_bytes: int = config.CORE_MOD_JAR_BYTES
    mod_metadata_bytes: int = config.CORE_MOD_METADATA_BYTES
    mod_archive_entries: int = config.CORE_MOD_ARCHIVE_ENTRIES
    mod_scan_entries: int = config.CORE_MOD_SCAN_ENTRIES
    mod_scan_bytes: int = config.CORE_MOD_SCAN_BYTES
    mod_nested_jar_bytes: int = config.CORE_MOD_NESTED_JAR_BYTES
    mod_nested_depth: int = config.CORE_MOD_NESTED_DEPTH
    mod_records: int = config.CORE_MOD_RECORDS
    mod_compression_ratio: int = config.CORE_MOD_COMPRESSION_RATIO
    mod_icon_bytes: int = config.CORE_MOD_ICON_BYTES
    mod_icon_dimension: int = config.CORE_MOD_ICON_DIMENSION
    mod_icon_pixels: int = config.CORE_MOD_ICON_PIXELS
    mod_icon_decoded_bytes: int = config.CORE_MOD_ICON_DECODED_BYTES
    mod_cache_entries: int = config.CORE_MOD_CACHE_ENTRIES
    mod_cache_bytes: int = config.CORE_MOD_CACHE_BYTES
    mod_icon_cache_directory: str = config.CORE_MOD_ICON_CACHE_DIRECTORY
    mrpack_archive_bytes: int = config.CORE_MRPACK_ARCHIVE_BYTES
    mrpack_index_bytes: int = config.CORE_MRPACK_INDEX_BYTES
    mrpack_archive_entries: int = config.CORE_MRPACK_ARCHIVE_ENTRIES
    mrpack_files: int = config.CORE_MRPACK_FILES
    mrpack_override_bytes: int = config.CORE_MRPACK_OVERRIDE_BYTES
    mrpack_overrides_bytes: int = config.CORE_MRPACK_OVERRIDES_BYTES
    mrpack_download_file_bytes: int = config.CORE_MRPACK_DOWNLOAD_FILE_BYTES
    mrpack_urls_per_file: int = config.CORE_MRPACK_URLS_PER_FILE
    mrpack_compression_ratio: int = config.CORE_MRPACK_COMPRESSION_RATIO
    mrpack_cache_entries: int = config.CORE_MRPACK_CACHE_ENTRIES
    mrpack_cache_bytes: int = config.CORE_MRPACK_CACHE_BYTES
    mrpack_allowed_download_hosts: tuple[str, ...] = config.CORE_MRPACK_ALLOWED_DOWNLOAD_HOSTS

    def __post_init__(self) -> None:
        if self.installer_process_timeout <= 0 or self.installer_archive_bytes < 1 or self.installer_archive_entries < 1:
            raise ValueError(diagnostic('settings.installer.limits.must.be.positive'))
        if self.download_workers < 1 or self.task_workers < 1 or type(self.network_connect_workers) is not int or self.network_connect_workers < 1:
            raise ValueError(diagnostic('settings.worker.counts.must.be.positive'))
        if not isfinite(self.download_item_interval) or self.download_item_interval <= 0:
            raise ValueError(diagnostic('settings.download.item.update.interval.must.be'))
        if any(not isfinite(value) or value <= 0 for value in (self.download_progress_interval, self.download_speed_window)):
            raise ValueError(diagnostic('settings.download.item.update.interval.must.be'))
        if type(self.download_retries) is not int or not 0 <= self.download_retries <= 5 or self.chunk_bytes < 1 or self.network_timeout <= 0:
            raise ValueError(diagnostic('settings.download.limits.must.be.positive'))
        if any(not isfinite(value) or value <= 0 for value in (self.network_timeout, self.network_connect_timeout, self.network_read_timeout)):
            raise ValueError(diagnostic('settings.download.limits.must.be.positive'))
        if self.maximum_metadata_bytes < 1 or self.maximum_native_bytes < 1:
            raise ValueError(diagnostic('settings.file.limits.must.be.positive'))
        if self.profile_depth_limit < 1 or self.retry_delay < 0 or self.java_probe_timeout <= 0 or self.client_shutdown_timeout <= 0:
            raise ValueError(diagnostic('settings.runtime.limits.must.be.positive'))
        if self.control_wait_interval <= 0:
            raise ValueError(diagnostic('settings.control.wait.interval.must.be.positive'))
        if any(type(value) is not int or value < 1 for value in (self.appearance_index_bytes, self.appearance_entry_bytes, self.appearance_pack_entries)):
            raise ValueError(diagnostic('settings.appearance.pack.limits.must.be.positive'))
        mod_limits = (self.mod_jar_bytes, self.mod_metadata_bytes, self.mod_archive_entries, self.mod_scan_entries, self.mod_scan_bytes, self.mod_nested_jar_bytes, self.mod_nested_depth, self.mod_records, self.mod_compression_ratio, self.mod_icon_bytes, self.mod_icon_dimension, self.mod_icon_pixels, self.mod_icon_decoded_bytes, self.mod_cache_entries, self.mod_cache_bytes)
        if any(type(value) is not int or value < 1 for value in mod_limits):
            raise ValueError(diagnostic('settings.mod.inspection.limits.must.be.positive'))
        mrpack_limits = (self.mrpack_archive_bytes, self.mrpack_index_bytes, self.mrpack_archive_entries, self.mrpack_files, self.mrpack_override_bytes, self.mrpack_overrides_bytes, self.mrpack_download_file_bytes, self.mrpack_urls_per_file, self.mrpack_compression_ratio, self.mrpack_cache_entries, self.mrpack_cache_bytes)
        if any(type(value) is not int or value < 1 for value in mrpack_limits):
            raise ValueError(diagnostic('settings.mrpack.inspection.limits.must.be.positive'))
        if not isinstance(self.mrpack_allowed_download_hosts, tuple) or any(not isinstance(host, str) or not host or host != host.lower() or ":" in host or "/" in host for host in self.mrpack_allowed_download_hosts):
            raise ValueError(diagnostic('settings.mrpack.download.hosts.require.an.immutable'))
