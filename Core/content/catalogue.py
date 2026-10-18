from Core.application.diagnostics import diagnostic
import json
from Core.content.versions import version_key

from dataclasses import asdict
from heapq import merge
from itertools import islice
from threading import RLock
from collections.abc import Iterator

from Core.application.application_contracts import ApplicationSnapshot, CatalogueSource, CatalogueState, CoreBrowseRequest, CoreBrowseResult, CoreChoice, VersionCatalogue
from Core.application.application_store import ApplicationStore
from Core.application.contracts import Cancelled, CoreError, CoreEvent, HttpRequest, InstallRequest
from Core.installation.installation import MetadataManager, core_identifier
from Core.game.metadata import object_value
from Core.network.network import NetworkManager
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager
from Core.application.tasks import Cancellation, TaskManager




class CatalogueManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._lock = RLock()
        self._sources: dict[str, CatalogueSource] = {}
        self._refresh_lock = RLock()
        self._revision = 0
        self._updating = False
        self._errors: tuple[str, ...] = ()
        self._installed: tuple[CoreChoice, ...] = ()
        self._startup_task = ""
        self._update_task = ""
        self._app.get("events", EventManager).subscribe("application", self._application_changed, deferred=False)

    def lookup(self, identifier: str) -> CoreChoice:
        with self._lock:
            sources = tuple(self._sources.values())
        for source in sources:
            for core in source.cores:
                if core.id == identifier:
                    return core
            for game in source.games:
                if source.loader == "Vanilla":
                    core = self.choice(game, "Vanilla", "")
                    if core.id == identifier:
                        return core
                elif identifier.startswith(core_identifier(InstallRequest(game, source.loader, "")).removesuffix("vanilla")):
                    for version in source.versions:
                        core = self.choice(game, source.loader, version)
                        if core.id == identifier:
                            return core
        raise CoreError(diagnostic('catalogue.unknown.catalogue.core'))

    def initialize(self) -> str:
        with self._lock:
            if not self._startup_task:
                self._startup_task = self.request_update()
            return self._startup_task

    def request_update(self) -> str:
        tasks = self._app.get("tasks", TaskManager)
        with self._lock:
            if self._update_task and any(task.task_id == self._update_task and task.state in ("queued", "running", "retrying", "paused", "cancelling") for task in tasks.snapshots()):
                return self._update_task
            if self._update_task and self._update_task != self._startup_task:
                tasks.release(self._update_task)
            self._update_task = tasks.submit("Refresh core catalogue", self._refresh_operation)
            return self._update_task

    def _refresh_operation(self, task_id: str, cancellation: Cancellation) -> CatalogueState:
        return self.refresh(cancellation)

    def state(self) -> CatalogueState:
        installed = self._app.get("application_store", ApplicationStore).snapshot().cores
        with self._lock:
            games = {core.minecraft for core in installed if core.installed}
            for source in self._sources.values():
                games.update(source.games)
                games.update(core.minecraft for core in source.cores)
            types = tuple(entry for source in self._sources.values() for entry in source.minecraft_types)
            return CatalogueState(self._revision, self._updating, tuple(sorted(games, key=version_key, reverse=True)), self._errors, types)

    def _publish_state(self) -> None:
        state = self.state()
        store = self._app.get("application_store", ApplicationStore)
        with store.lock:
            store.minecraft_versions = state.minecraft_versions
            store.publish()
        self._app.get("events", EventManager).publish(CoreEvent("core.catalogue", state))

    def _application_changed(self, event: CoreEvent) -> None:
        if not isinstance(event.payload, ApplicationSnapshot):
            return
        installed = tuple(core for core in event.payload.cores if core.installed)
        with self._lock:
            if installed == self._installed:
                return
            self._installed = installed
            self._revision += 1
        self._publish_state()

    def refresh(self, cancellation: Cancellation) -> CatalogueState:
        with self._refresh_lock:
            with self._lock:
                self._sources = {}
                self._errors = ()
                self._updating = True
                self._revision += 1
            self._publish_state()
            sources = {}
            errors = []
            try:
                files = self._app.get("files", FileManager)
                for loader in ("Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"):
                    cancellation.check()
                    try:
                        source = self.fetch_source(loader, cancellation)
                        path = f"{self._config.cores_directory}/{self._config.cache_directory}/{self._config.application_catalog_filename}.{loader.lower()}"
                        files.write_json(path, asdict(source))
                        sources[loader] = source
                    except Cancelled:
                        raise
                    except (CoreError, OSError, ValueError, KeyError, TypeError) as error:
                        errors.append(loader + ": " + str(error))
            except Cancelled:
                sources = {}
                raise
            finally:
                with self._lock:
                    self._sources = sources
                    self._errors = tuple(errors)
                    self._updating = False
                    self._revision += 1
                self._publish_state()
            return self.state()

    def source(self, loader: str) -> CatalogueSource:
        with self._lock:
            return self._sources.get(loader, CatalogueSource(loader))

    def versions(self, loader: str, minecraft: str) -> VersionCatalogue:
        if loader not in ("Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"):
            raise CoreError(diagnostic('catalogue.unknown.loader'))
        if loader != "Vanilla" and not minecraft:
            raise CoreError(diagnostic('catalogue.minecraft.version.is.required.for.loader'))
        installed = self._app.get("application_store", ApplicationStore).snapshot().cores
        request = CoreBrowseRequest("versions", loader=loader, minecraft="" if loader == "Vanilla" else minecraft)
        with self._lock:
            source = self._sources.get(loader, CatalogueSource(loader))
            revision = self._revision
        choices = {core.id: core for core in self.source_choices(source, request, {})}
        choices.update((core.id, core) for core in installed if core.installed and self.matches(core, request))
        result = tuple(sorted(choices.values(), key=lambda core: (core.installed, version_key(core.minecraft), version_key(core.version)), reverse=True))
        return VersionCatalogue(loader, request.minecraft, result, revision)

    def close(self) -> None:
        self._app.get("events", EventManager).unsubscribe("application", self._application_changed)

    def fetch_source(self, loader: str, cancellation: Cancellation) -> CatalogueSource:
        network = self._app.get("network", NetworkManager)
        if loader == "Vanilla":
            entries = self._app.get("metadata", MetadataManager).catalogue(cancellation)
            return CatalogueSource(loader, tuple(item.version_id for item in entries), minecraft_types=tuple((item.version_id, item.version_type) for item in entries))
        if loader in ("Fabric", "Quilt"):
            base = self._config.fabric_meta_url if loader == "Fabric" else self._config.quilt_meta_url
            games = json.loads(network.read(HttpRequest(base + "/versions/game"), cancellation, self._config.maximum_metadata_bytes))
            versions = json.loads(network.read(HttpRequest(base + "/versions/loader"), cancellation, self._config.maximum_metadata_bytes))
            return CatalogueSource(loader, tuple(item["version"] for item in games), tuple(item["version"] for item in versions))
        if loader == "Forge":
            data = object_value(json.loads(network.read(HttpRequest(self._config.forge_catalog_url), cancellation, self._config.maximum_metadata_bytes)), "Forge catalogue")
            cores = tuple(self.choice(game, loader, version.removeprefix(game + "-")) for game, versions in data.items() for version in versions)
            return CatalogueSource(loader, cores=cores)
        if loader == "NeoForge":
            data = object_value(json.loads(network.read(HttpRequest(self._config.neoforge_catalog_url), cancellation, self._config.maximum_metadata_bytes)), "NeoForge catalogue")
            cores = tuple(self.choice(requirement["equals"], loader, item["version"]) for item in data["versions"] for requirement in item.get("requires", []) if requirement.get("uid") == "net.minecraft" and requirement.get("equals"))
            return CatalogueSource(loader, cores=cores)
        raise CoreError(diagnostic('catalogue.unknown.loader'))

    def browse(self, request: CoreBrowseRequest, active: tuple[str, ...], cancellation: Cancellation) -> CoreBrowseResult:
        loaders = ("Vanilla", "Fabric", "Forge", "NeoForge", "Quilt")
        if request.loader and request.loader not in loaders or request.state not in ("all", "installed", "available") or request.offset < 0 or request.limit < 1:
            raise CoreError(diagnostic('catalogue.invalid.core.browser.request'))
        snapshot = self._app.get("application_store", ApplicationStore).snapshot()
        with self._lock:
            sources = tuple(self._sources[loader] for loader in loaders if loader in self._sources and (not request.loader or request.loader == loader)) if request.state != "installed" else ()
            errors = self._errors
        games = self.state().minecraft_versions
        ranks = {game: len(games) - index for index, game in enumerate(games)}
        preferred = tuple(core for core in snapshot.cores if (core.installed or core.id in active) and self.matches(core, request))
        preferred = tuple(sorted(preferred, key=lambda core: self.order(core, ranks), reverse=True))
        known = {core.id for core in preferred}
        candidates = merge(*(self.source_choices(source, request, ranks) for source in sources), key=lambda core: self.order(core, ranks), reverse=True)
        choices = self.browse_choices(preferred, candidates, known, cancellation)
        result = tuple(islice(choices, request.offset, request.offset + request.limit + 1))
        return CoreBrowseResult(request.request_id, request.offset, result[:request.limit], len(result) > request.limit, tuple(errors), games)

    @staticmethod
    def matches(core: CoreChoice, request: CoreBrowseRequest) -> bool:
        return (not request.loader or core.loader == request.loader) and (not request.minecraft or core.minecraft == request.minecraft) and (request.state == "all" or core.installed == (request.state == "installed"))

    @staticmethod
    def order(core: CoreChoice, ranks: dict[str, int]) -> tuple:
        return ranks.get(core.minecraft, 0), version_key(core.minecraft), version_key(core.version), core.loader, core.id

    def source_choices(self, source: CatalogueSource, request: CoreBrowseRequest, ranks: dict[str, int]) -> Iterator[CoreChoice]:
        if source.cores:
            yield from sorted((core for core in source.cores if self.matches(core, request)), key=lambda core: self.order(core, ranks), reverse=True)
            return
        games = sorted((game for game in source.games if not request.minecraft or game == request.minecraft), key=lambda game: (ranks.get(game, 0), version_key(game)), reverse=True)
        if source.loader == "Vanilla":
            for game in games:
                yield self.choice(game, "Vanilla", "")
            return
        versions = sorted(source.versions, key=version_key, reverse=True)
        for game in games:
            for version in versions:
                yield self.choice(game, source.loader, version)

    @staticmethod
    def browse_choices(preferred: tuple[CoreChoice, ...], candidates: Iterator[CoreChoice], known: set[str], cancellation: Cancellation) -> Iterator[CoreChoice]:
        yield from preferred
        for core in candidates:
            cancellation.check()
            if core.id not in known:
                known.add(core.id)
                yield core

    @staticmethod
    def choice(minecraft: str, loader: str, version: str) -> CoreChoice:
        return CoreChoice(core_identifier(InstallRequest(minecraft, loader, version)), minecraft, loader, version)
