from dataclasses import dataclass, replace

from Core.application.contracts import Artifact, VersionProfile
from Core.application.router import AccessManager, AppManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager, safe_identifier
from Core.application.tasks import Cancellation, TaskManager
from Core.game.metadata import asset_mappings, object_value


@dataclass(frozen=True)
class MaterializedAssets:
    directory: str
    artifacts: tuple[Artifact, ...] = ()


class AssetManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config

    def materialize(self, profile: VersionProfile, cancellation: Cancellation, build_id: str = "", task_id: str = "") -> MaterializedAssets:
        cancellation.check()
        root = self._config.libs_directory + "/assets"
        if profile.asset_index is None:
            return MaterializedAssets(root)
        files = self._app.get("files", FileManager)
        index = object_value(files.json(profile.asset_index.artifact.relative_path), "asset index")
        mappings = asset_mappings(index, self._config)
        destinations = []
        if index.get("virtual", False):
            safe_identifier(profile.asset_index.index_id)
            destinations.append(root + "/virtual/" + profile.asset_index.index_id)
        if index.get("map_to_resources", False) and build_id:
            safe_identifier(build_id)
            destinations.append(self._config.builds_directory + "/" + build_id + "/resources")
        artifacts = []
        total = sum(artifact.size for name, artifact in mappings) * len(destinations)
        completed = 0
        for destination in destinations:
            with self._app.get("access", AccessManager).access("assets:" + str(files.path(destination)).casefold(), cancellation):
                files.ensure_directory(destination)
                for name, source in mappings:
                    cancellation.check()
                    target = replace(source, url="", relative_path=destination + "/" + name)
                    if not files.cached(target, cancellation):
                        files.copy_file(source.relative_path, target, cancellation)
                    artifacts.append(target)
                    completed += target.size
                    if task_id:
                        self._app.get("tasks", TaskManager).progress(task_id, completed, total)
        return MaterializedAssets(destinations[-1] if destinations else root, tuple(artifacts))
