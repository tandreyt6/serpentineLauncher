from Core.application.diagnostics import diagnostic
from dataclasses import asdict, replace
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

from Core.application.contracts import Artifact, CoreError, CoreEvent, CoreInstallation, Digest, DownloadBatch, HttpRequest, InstalledCore, InstallRequest, TaskStage, VersionEntry, VersionProfile
from Core.network.downloads import DownloadManager
from Core.installation.forge_installation import ForgeInstallerManager
from Core.game.metadata import asset_artifacts, host_platform, manifest_entries, merge_profiles, object_value, parse_json, parse_profile, profile_artifacts
from Core.network.network import NetworkManager
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager, safe_identifier
from Core.application.tasks import Cancellation, TaskManager


def core_identifier(request: InstallRequest) -> str:
    version = quote(request.minecraft_version, safe="")
    loader_version = quote(request.loader_version, safe="")
    return safe_identifier(f"{request.loader.lower()}-{version}-{loader_version or 'vanilla'}")


class MetadataManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config

    def catalogue(self, cancellation: Cancellation) -> tuple[VersionEntry, ...]:
        data = self._app.get("network", NetworkManager).read(HttpRequest(self._config.manifest_url), cancellation, self._config.maximum_metadata_bytes)
        return manifest_entries(parse_json(data), self._config)

    def submit_catalogue(self) -> str:
        return self._app.get("tasks", TaskManager).submit("Minecraft versions", self._catalogue_operation)

    def _catalogue_operation(self, task_id: str, cancellation: Cancellation) -> tuple[VersionEntry, ...]:
        return self.catalogue(cancellation)

    def load_profile(self, relative_path: str, ancestry: tuple[str, ...] = ()) -> VersionProfile:
        files = self._app.get("files", FileManager)
        profile = parse_profile(object_value(files.json(relative_path), "profile"), self._config)
        if profile.version_id in ancestry or len(ancestry) >= self._config.profile_depth_limit:
            raise CoreError(diagnostic('installation.profile.inheritance.cycle.or.depth.limit'))
        if profile.parent_id:
            parent_path = f"{self._config.cores_directory}/{self._config.cache_directory}/versions/{profile.parent_id}/{profile.parent_id}.json"
            parent = self.load_profile(parent_path, (*ancestry, profile.version_id))
            return merge_profiles(parent, profile)
        return profile

    def close(self) -> None:
        pass


class InstallationManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._lock = RLock()
        self._active: dict[str, CoreInstallation] = {}
        self._migrated = False
        self._resources_task = ""

    def submit(self, request: InstallRequest) -> str:
        if request.loader not in ("Vanilla", "Fabric", "Quilt", "Forge", "NeoForge"):
            raise CoreError(diagnostic('installation.unknown.loader'))
        if request.loader != "Vanilla" and not request.loader_version:
            raise CoreError(diagnostic('installation.loader.version.is.required'))
        core_id = core_identifier(request)
        with self._lock:
            tasks = self._app.get("tasks", TaskManager)
            active = {item.task_id for item in tasks.snapshots() if item.state in ("queued", "running", "retrying", "paused", "cancelling")}
            existing = self._active.get(core_id.casefold())
            if existing and existing.task_id in active:
                return existing.task_id
            if existing and any(item.task_id == existing.task_id and item.state == 'failed' for item in tasks.snapshots()) and tasks.retry(existing.task_id):
                return existing.task_id
            dependencies = ()
            if request.loader != "Vanilla":
                vanilla = InstallRequest(request.minecraft_version)
                parent_id = core_identifier(vanilla)
                if not self.ready(parent_id):
                    dependencies = (self.submit(vanilla),)
            stages = (TaskStage("metadata"),) + ((TaskStage("installer"),) if request.loader in ("Forge", "NeoForge") else ()) + (TaskStage("libraries"), TaskStage("assets"), TaskStage("finalize"))
            task = tasks.submit(f"Install {core_id}", InstallationOperation(self._app, request).run, dependencies, stages, retryable=True)
            installation = CoreInstallation(core_id, request.minecraft_version, request.loader, request.loader_version, task)
            self._active[core_id.casefold()] = installation
            self._app.get("events", EventManager).publish(CoreEvent("core.queued", installation))
            return task

    def tasks(self) -> tuple[CoreInstallation, ...]:
        with self._lock:
            return tuple(self._active.values())

    def ready(self, core_id: str) -> bool:
        safe_identifier(core_id)
        tasks = self._app.get("tasks", TaskManager)
        if any(item.title == "Install " + core_id and item.state in ("queued", "running", "retrying", "paused", "cancelling") for item in tasks.snapshots()):
            return False
        files = self._app.get("files", FileManager)
        marker = f"{self._config.cores_directory}/{core_id}/{self._config.install_metadata_filename}"
        if not files.exists(marker):
            return False
        receipt = self.receipt(core_id)
        if not files.exists(receipt.profile_path):
            return False
        try:
            profile = self._app.get("metadata", MetadataManager).load_profile(receipt.profile_path)
        except (OSError, ValueError, TypeError, CoreError):
            return False
        if profile.asset_index and not files.is_directory(f"{self._config.libs_directory}/assets/objects"):
            return False
        if receipt.loader != "Vanilla" and not self.ready(core_identifier(InstallRequest(receipt.minecraft_version))):
            return False
        return all(files.available(artifact) for artifact in profile_artifacts(profile, host_platform()))

    def migrate(self, cancellation: Cancellation) -> None:
        with self._lock:
            if self._migrated:
                return
            files = self._app.get("files", FileManager)
            cache = f"{self._config.cores_directory}/{self._config.cache_directory}"
            files.merge_directory(f"{cache}/assets", f"{self._config.libs_directory}/assets", cancellation)
            for name, folder, _ in files.entries(cache + "/versions", recursive=True):
                cancellation.check()
                if folder or not name.endswith(".json"):
                    continue
                profile = self._migration_profile(files, cache + "/versions/" + name)
                if profile is None or profile.parent_id or profile.client is None:
                    continue
                for artifact in profile_artifacts(profile, host_platform()):
                    if not artifact.relative_path.startswith(self._config.libs_directory + "/libraries/"):
                        continue
                    legacy = cache + "/libraries/" + artifact.relative_path.split("/libraries/", 1)[1]
                    if files.exists(legacy) and not files.exists(artifact.relative_path):
                        files.rename_file(legacy, artifact.relative_path)
            for name, folder, _ in files.entries(self._config.cores_directory):
                path = f"{self._config.cores_directory}/{name}/{self._config.profile_filename}"
                if not folder or not files.exists(path):
                    continue
                profile = self._migration_profile(files, path)
                if profile is None:
                    continue
                if not profile.parent_id:
                    marker = f"{self._config.cores_directory}/{name}/{self._config.install_metadata_filename}"
                    if files.exists(marker) and profile.asset_index and files.is_directory(self._config.libs_directory + "/assets/objects") and all(files.available(artifact) for artifact in profile_artifacts(profile, host_platform())):
                        self.record_resources(profile)
                    continue
                for library in profile.libraries:
                    if library.artifact:
                        artifact = library.artifact
                        legacy = self._config.libs_directory + "/libraries/" + artifact.relative_path.split("/libraries/", 1)[1]
                        if files.exists(legacy) and not files.exists(artifact.relative_path):
                            files.rename_file(legacy, artifact.relative_path)
            self._migrated = True

    def _migration_profile(self, files: FileManager, path: str) -> VersionProfile | None:
        try:
            return parse_profile(object_value(files.json(path), "migration profile"), self._config)
        except (OSError, ValueError, TypeError, CoreError):
            self._app.log("Skipped invalid profile during resource migration: " + path, "WARNING")
            return None

    def prepare_resources(self) -> str:
        with self._lock:
            files = self._app.get("files", FileManager)
            marker = f"{self._config.libs_directory}/{self._config.resources_metadata_filename}"
            if self._resources_ready(files, marker):
                return ""
            tasks = self._app.get("tasks", TaskManager)
            if any(item.task_id == self._resources_task and item.state in ("queued", "running", "retrying", "paused", "cancelling") for item in tasks.snapshots()):
                return self._resources_task
            if self._resources_task and any(item.task_id == self._resources_task and item.state == 'failed' for item in tasks.snapshots()) and tasks.retry(self._resources_task):
                return self._resources_task
            stages = tuple(TaskStage(key) for key in ("metadata", "libraries", "assets", "finalize"))
            self._resources_task = tasks.submit("Prepare Minecraft resources", ResourcePreparationOperation(self._app).run, stages=stages, retryable=True)
            return self._resources_task

    def _resources_ready(self, files: FileManager, marker: str) -> bool:
        if not files.exists(marker):
            return False
        try:
            value = object_value(files.json(marker), "shared resource receipt")
            index = value.get("asset_index_path")
            return value.get("schema") == 1 and isinstance(index, str) and index.startswith(self._config.libs_directory + "/assets/indexes/") and files.exists(index) and files.is_directory(f"{self._config.libs_directory}/assets/objects") and files.is_directory(f"{self._config.libs_directory}/libraries")
        except (OSError, ValueError, TypeError, CoreError):
            return False

    def record_resources(self, profile: VersionProfile) -> None:
        if profile.asset_index is None:
            return
        with self._lock:
            files = self._app.get("files", FileManager)
            marker = f"{self._config.libs_directory}/{self._config.resources_metadata_filename}"
            if not self._resources_ready(files, marker):
                files.write_json(marker, {"schema": 1, "minecraft_version": profile.version_id, "asset_index_path": profile.asset_index.artifact.relative_path})

    def receipt(self, core_id: str) -> InstalledCore:
        safe_identifier(core_id)
        value = object_value(self._app.get("files", FileManager).json(f"{self._config.cores_directory}/{core_id}/{self._config.install_metadata_filename}"), "core receipt")
        receipt = InstalledCore(**value)
        if receipt.core_id != core_id:
            raise CoreError(diagnostic('installation.core.receipt.identity.mismatch'))
        return receipt

    def integrity(self, core_id: str) -> tuple[Artifact, ...]:
        safe_identifier(core_id)
        value = self._app.get("files", FileManager).json(f"{self._config.cores_directory}/{core_id}/{self._config.integrity_filename}")
        if not isinstance(value, list):
            raise CoreError(diagnostic('installation.invalid.installed.core.integrity.inventory'))
        artifacts = []
        for item in value:
            entry = object_value(item, "integrity artifact")
            path = entry["relative_path"]
            prefix = f"{self._config.cores_directory}/{self._config.cache_directory}/"
            if path.startswith((prefix + "libraries/", prefix + "assets/")):
                shared = self._config.libs_directory + "/" + path.removeprefix(prefix)
                if not self._app.get("files", FileManager).exists(path):
                    path = shared
            elif path.startswith(self._config.libs_directory + "/libraries/") and not self._app.get("files", FileManager).exists(path):
                path = prefix + "libraries/" + path.split("/libraries/", 1)[1]
            artifacts.append(Artifact(entry["url"], path, entry["size"], tuple(Digest(**digest) for digest in entry["digests"])))
        return tuple(artifacts)

    def close(self) -> None:
        with self._lock:
            self._active.clear()


class InstallationOperation:
    def __init__(self, app: AppManager, request: InstallRequest) -> None:
        self._app = app
        self._request = request

    def run(self, task_id: str, cancellation: Cancellation) -> InstalledCore:
        core_id = core_identifier(self._request)
        cancellation.check()
        return self._install(task_id, cancellation, core_id)

    def _install(self, task_id: str, cancellation: Cancellation, core_id: str) -> InstalledCore:
        config = self._app.get("config", CoreConfig)
        files = self._app.get("files", FileManager)
        tasks = self._app.get("tasks", TaskManager)
        tasks.start_stage(task_id, "metadata")
        self._app.get("installation", InstallationManager).migrate(cancellation)
        files.remove_file(f"{config.cores_directory}/{core_id}/{config.install_metadata_filename}")
        downloads = self._app.get("downloads", DownloadManager)
        metadata = self._app.get("metadata", MetadataManager)
        versions = metadata.catalogue(cancellation)
        entry = next((item for item in versions if item.version_id == self._request.minecraft_version), None)
        if entry is None:
            raise CoreError(diagnostic('installation.minecraft.version.is.absent.from.the'))
        downloads.fetch(entry.artifact, cancellation)
        parent_data = object_value(files.json(entry.artifact.relative_path), "parent profile")
        profile = parse_profile(parent_data, config)
        if profile.version_id != self._request.minecraft_version or profile.parent_id:
            raise CoreError(diagnostic('installation.vanilla.profile.identity.mismatch'))
        effective = profile
        raw_profile = parent_data
        installer_artifacts = ()
        if self._request.loader in ("Forge", "NeoForge"):
            tasks.start_stage(task_id, "installer")
            result = self._app.get("forge_installers", ForgeInstallerManager).install(self._request, profile, files.read(entry.artifact.relative_path), task_id, cancellation)
            raw_profile = parse_json(result.profile)
            raw_profile["downloads"] = {**object_value(raw_profile.get("downloads", {}), "loader downloads"), "client": parent_data["downloads"]["client"]}
            effective = merge_profiles(profile, parse_profile(raw_profile, config))
            if effective.client is None or profile.client is None:
                raise CoreError(diagnostic('installation.installer.requires.a.minecraft.client.artifact'))
            if not files.cached(effective.client, cancellation):
                files.copy_file(profile.client.relative_path, effective.client, cancellation)
            installer_artifacts = result.artifacts
        elif self._request.loader != "Vanilla":
            base = config.fabric_meta_url if self._request.loader == "Fabric" else config.quilt_meta_url
            minecraft = quote(self._request.minecraft_version, safe="")
            loader = quote(self._request.loader_version, safe="")
            url = f"{base.rstrip('/')}/versions/loader/{minecraft}/{loader}/profile/json"
            raw_profile = parse_json(self._app.get("network", NetworkManager).read(HttpRequest(url), cancellation, config.maximum_metadata_bytes))
            child = parse_profile(raw_profile, config)
            if child.parent_id != profile.version_id:
                raise CoreError(diagnostic('installation.loader.metadata.must.inherit.the.requested'))
            effective = merge_profiles(profile, child)
        tasks.start_stage(task_id, "libraries")
        artifacts = profile_artifacts(effective, host_platform())
        verified = [entry.artifact, *installer_artifacts]
        def verified_artifact(artifact):
            cancellation.check()
            if not artifact.digests and "/libraries/" in artifact.relative_path:
                checksum = self._app.get("network", NetworkManager).read(HttpRequest(artifact.url + ".sha1"), cancellation, 4096).decode("ascii").strip().split()[0]
                artifact = replace(artifact, digests=(Digest("sha1", checksum),))
            return artifact
        with ThreadPoolExecutor(max_workers=config.download_workers, thread_name_prefix='launcher-checksum') as executor:
            verified.extend(executor.map(verified_artifact, artifacts))
        downloads.execute(DownloadBatch(tuple(artifact for artifact in verified if artifact.url), "Core artifacts"), task_id, cancellation)
        for artifact in verified:
            if not files.verify(artifact, cancellation):
                raise CoreError(diagnostic('installation.installed.core.artifact.failed.verification'))
        tasks.start_stage(task_id, "assets")
        if effective.asset_index:
            index = object_value(files.json(effective.asset_index.artifact.relative_path), "asset index")
            assets = asset_artifacts(index, config)
            downloads.execute(DownloadBatch(assets, "Assets"), task_id, cancellation)
            verified.extend(assets)
        cancellation.check()
        tasks.start_stage(task_id, "finalize")
        self._app.get("installation", InstallationManager).record_resources(profile)
        profile_path = f"{config.cores_directory}/{core_id}/{config.profile_filename}"
        files.write_json(profile_path, raw_profile)
        receipt = InstalledCore(core_id, self._request.minecraft_version, self._request.loader, self._request.loader_version, profile_path)
        files.write_json(f"{config.cores_directory}/{core_id}/{config.integrity_filename}", [asdict(artifact) for artifact in verified])
        files.write_json(f"{config.cores_directory}/{core_id}/{config.install_metadata_filename}", asdict(receipt))
        self._app.get("events", EventManager).publish(CoreEvent("core.installed", receipt))
        return receipt


class ResourcePreparationOperation:
    def __init__(self, app: AppManager) -> None:
        self._app = app

    def run(self, task_id: str, cancellation: Cancellation) -> str:
        config = self._app.get("config", CoreConfig)
        files = self._app.get("files", FileManager)
        tasks = self._app.get("tasks", TaskManager)
        tasks.start_stage(task_id, "metadata")
        self._app.get("installation", InstallationManager).migrate(cancellation)
        versions = self._app.get("metadata", MetadataManager).catalogue(cancellation)
        entry = next((item for item in versions if item.version_type == "release"), None)
        if entry is None:
            raise CoreError(diagnostic('installation.no.stable.minecraft.version.is.available'))
        downloads = self._app.get("downloads", DownloadManager)
        downloads.fetch(entry.artifact, cancellation)
        profile = parse_profile(object_value(files.json(entry.artifact.relative_path), "resource profile"), config)
        if profile.version_id != entry.version_id or profile.parent_id or profile.asset_index is None:
            raise CoreError(diagnostic('installation.invalid.minecraft.profile.for.resource.preparation'))
        artifacts = tuple(artifact for artifact in profile_artifacts(profile, host_platform()) if artifact != profile.client)
        tasks.start_stage(task_id, "libraries")
        downloads.execute(DownloadBatch(artifacts, "Shared Minecraft libraries"), task_id, cancellation)
        index = object_value(files.json(profile.asset_index.artifact.relative_path), "asset index")
        tasks.start_stage(task_id, "assets")
        downloads.execute(DownloadBatch(asset_artifacts(index, config), "Shared Minecraft assets"), task_id, cancellation)
        cancellation.check()
        tasks.start_stage(task_id, "finalize")
        self._app.get("installation", InstallationManager).record_resources(profile)
        return profile.version_id
