from Core.application.diagnostics import diagnostic
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from Core.configuration.settings import THEME_SCENE_BYTES
from tempfile import TemporaryDirectory, gettempdir
import json

from universal_gui.pack.format import validate_key

from Core.application.tasks import Cancellation
from Core.application.router import AppManager


@dataclass(frozen=True)
class ThemeSceneRequest:
    theme_id: str
    source: Path
    framework_source: Path
    manifest: bytes
    resources: tuple[tuple[str, bytes], ...]


@dataclass(frozen=True)
class ThemeSceneBundle:
    theme_id: str
    directory: Path | None
    signature: str
    views: tuple[str, ...] = ()
    framework_views: tuple[str, ...] = ()


@dataclass(frozen=True)
class StartupPreferences:
    theme: str = ""
    hardware_acceleration: bool = True
    locale: str = ""


def scene_configuration(manifest: dict) -> tuple[str, str]:
    configuration = manifest.get("launcher")
    if configuration is None:
        return "", ""
    if not isinstance(configuration, dict) or type(configuration.get("api")) is not int or configuration["api"] != 1:
        raise ValueError(diagnostic('theme_scenes.launcher.theme.api.must.be'))
    unknown = configuration.keys() - {"api", "viewsRoot", "frameworkRoot"}
    if unknown:
        raise ValueError("Unknown launcher theme fields: " + ", ".join(sorted(unknown)))
    roots = tuple(configuration.get(key, "") for key in ("viewsRoot", "frameworkRoot"))
    for root in roots:
        if not isinstance(root, str):
            raise ValueError(diagnostic('theme_scenes.scene.root.must.be.a.relative'))
        if root:
            validate_key(root)
    return roots


class ThemeSceneDriver:
    def __init__(self, cache_directory: Path | None = None) -> None:
        self._directories: list[TemporaryDirectory] = []
        self._bundles: dict[str, ThemeSceneBundle] = {}
        self._cache_directory = cache_directory or Path(gettempdir()) / "serpantine-ui-cache"

    def prepare(self, request: ThemeSceneRequest, cancellation: Cancellation) -> ThemeSceneBundle:
        root, framework_root = scene_configuration(json.loads(request.manifest))
        files = dict(request.resources)
        views = tuple(sorted(key[len(root) + 1:] for key in files if root and key.startswith(root + "/")))
        framework_views = tuple(sorted(key[len(framework_root) + 1:] for key in files if framework_root and key.startswith(framework_root + "/")))
        if root and not views:
            raise ValueError("viewsRoot contains no resources: " + root)
        if framework_root and not framework_views:
            raise ValueError("frameworkRoot contains no resources: " + framework_root)
        if not views and not framework_views:
            return ThemeSceneBundle(request.theme_id, None, "")
        if sum(len(content) for content in files.values()) > THEME_SCENE_BYTES:
            raise ValueError(diagnostic('theme_scenes.launcher.scene.resources.exceed.mib'))
        prepared = {}
        for source, entries, target in ((request.source, views, "views"), (request.framework_source, framework_views, "framework")):
            if entries:
                for path in sorted(source.rglob("*")):
                    cancellation.check()
                    if path.is_file() and not any(part == "__pycache__" for part in path.relative_to(source).parts) and path.suffix not in (".pyc", ".tmp"):
                        prepared[target + "/" + path.relative_to(source).as_posix()] = path.read_bytes()
        for prefix, entries, target in ((root, views, "views"), (framework_root, framework_views, "framework")):
            for key in entries:
                validate_key(key)
                prepared[target + "/" + key] = files[prefix + "/" + key]
        signature = sha256(b"".join(key.encode() + b"\0" + sha256(content).digest() for key, content in sorted(prepared.items()))).hexdigest()
        if signature in self._bundles:
            return replace(self._bundles[signature], theme_id=request.theme_id, views=views, framework_views=framework_views)
        cached = self._cache_directory / signature
        try:
            if cached.is_dir() and all((cached / key).is_file() and (cached / key).read_bytes() == content for key, content in prepared.items()):
                bundle = ThemeSceneBundle(request.theme_id, cached, signature, views, framework_views)
                self._bundles[signature] = bundle
                return bundle
        except OSError:
            pass
        temporary = TemporaryDirectory(prefix="serpantine-theme-")
        directory = Path(temporary.name)
        try:
            for key, content in prepared.items():
                cancellation.check()
                destination = directory / key
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            try:
                self._cache_directory.mkdir(parents=True, exist_ok=True)
                if not cached.exists() and cached.resolve().is_relative_to(self._cache_directory.resolve()):
                    directory.rename(cached)
                    directory = cached
            except OSError:
                pass
        except Exception:
            temporary.cleanup()
            raise
        self._directories.append(temporary)
        bundle = ThemeSceneBundle(request.theme_id, directory, signature, views, framework_views)
        self._bundles[signature] = bundle
        return bundle

    def startup_preferences(self, root: Path, filename: str, maximum: int) -> StartupPreferences:
        path = root / filename
        if not path.is_file():
            return StartupPreferences()
        with path.open("rb") as stream:
            content = stream.read(maximum + 1)
        if len(content) > maximum:
            raise ValueError(diagnostic('theme_scenes.application.state.exceeds.size.limit'))
        settings = json.loads(content).get("settings", {})
        theme = settings.get("theme", "")
        acceleration = settings.get("hardwareAcceleration", True)
        locale = settings.get("locale", "")
        return StartupPreferences(theme if isinstance(theme, str) else "", acceleration if type(acceleration) is bool else True, locale if isinstance(locale, str) else "")

    def close(self) -> None:
        for directory in reversed(self._directories):
            directory.cleanup()
        self._directories.clear()
        self._bundles.clear()


class ThemeSceneOperation:
    def __init__(self, app: AppManager, request: ThemeSceneRequest) -> None:
        self._app = app
        self._request = request

    def run(self, task_id: str, cancellation: Cancellation) -> ThemeSceneBundle:
        return self._app.get("theme_scenes", ThemeSceneDriver).prepare(self._request, cancellation)


class StartupPreferencesOperation:
    def __init__(self, app: AppManager, root: Path, filename: str, maximum: int) -> None:
        self._app = app
        self._root = root
        self._filename = filename
        self._maximum = maximum

    def run(self, task_id: str, cancellation: Cancellation) -> StartupPreferences:
        cancellation.check()
        return self._app.get("theme_scenes", ThemeSceneDriver).startup_preferences(self._root, self._filename, self._maximum)
