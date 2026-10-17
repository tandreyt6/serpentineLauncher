from Core.application.diagnostics import diagnostic
import json
from pathlib import Path
from zlib import error as CompressionError

from universal_gui.pack.format import PackLimits, ThemePack

from Core.application.application_contracts import AppearanceCatalogue, AppearanceScanRequest, LanguagePack, ThemeFile, VisualResources, VisualResourcesRequest
from Core.application.router import AppManager
from Core.application.settings import CoreConfig
from Core.application.tasks import Cancellation
from Core.appearance.theme_scenes import scene_configuration
from Core.appearance.theme_metadata import theme_icon_key
from Core.resources.runtime import ResourcePath, embedded


class AppearanceFileDriver:
    def __init__(self, config: CoreConfig) -> None:
        self._config = config

    def _read(self, path: Path, maximum: int) -> bytes:
        with path.open("rb") as stream:
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError(diagnostic('appearance_packs.visual.resource.exceeds.size.limit'))
        return data

    def prepare(self, request: VisualResourcesRequest, cancellation: Cancellation) -> VisualResources:
        pending_themes = []
        for directory in (request.assets / "themes", request.themes):
            for pending in directory.glob("*.ugtheme" + request.pending_suffix):
                cancellation.check()
                try:
                    pending.replace(pending.with_suffix(""))
                except PermissionError:
                    pending_themes.append(pending)
        languages = self.scan(AppearanceScanRequest("languages", (request.assets / "locales", request.languages)), cancellation)
        icons = []
        for path in sorted((request.assets / "icons").glob("*.png")) + sorted((request.assets / "icons").glob("*.svg")):
            cancellation.check()
            icons.append((path.stem, path))
        images = tuple((path.stem, path) for path in sorted((request.assets / "images").glob("*.png")))
        return VisualResources(languages.languages, tuple(icons), images, tuple(pending_themes), languages.errors)

    def scan(self, request: AppearanceScanRequest, cancellation: Cancellation) -> AppearanceCatalogue:
        if request.kind not in ("languages", "themes"):
            raise ValueError(diagnostic('appearance_packs.unknown.appearance.catalogue'))
        languages = {}
        themes = {}
        errors = []
        pattern = "*.json" if request.kind == "languages" else "*.ugtheme"
        for directory in request.directories:
            paths = sorted(directory.glob(pattern))
            if request.kind == "themes" and request.pending_suffix:
                paths.extend(sorted(directory.glob(pattern + request.pending_suffix)))
            for path in paths:
                cancellation.check()
                try:
                    if request.kind == "languages":
                        if embedded() and path.stem == "en" and not isinstance(path, ResourcePath):
                            raise ValueError(diagnostic('appearance_packs.built.in.english.cannot.be.replaced'))
                        with path.open("rb") as stream:
                            data = stream.read(self._config.appearance_index_bytes + 1)
                        if len(data) > self._config.appearance_index_bytes:
                            raise ValueError(diagnostic('appearance_packs.language.pack.exceeds.size.limit'))
                        entries = json.loads(data.decode("utf-8-sig"))
                        if not isinstance(entries, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in entries.items()):
                            raise ValueError(diagnostic('appearance_packs.language.pack.must.map.text.keys'))
                        languages[path.stem] = LanguagePack(path.stem, tuple(entries.items()))
                    else:
                        limits = PackLimits(self._config.appearance_index_bytes, self._config.appearance_entry_bytes, self._config.appearance_pack_entries)
                        pack = ThemePack(path, limits)
                        try:
                            manifest = json.loads(pack.read("manifest.json"))
                            for root in scene_configuration(manifest):
                                if root and not any(key.startswith(root + "/") for key in pack.keys()):
                                    raise ValueError("Scene root contains no resources: " + root)
                            icon_key = ''
                            try:
                                icon_key = theme_icon_key(manifest)
                                if icon_key:
                                    pack.read(icon_key)
                            except (ValueError, KeyError, CompressionError) as error:
                                icon_key = ''
                                errors.append(f"{path.name}: {error}")
                        finally:
                            pack.close()
                        identity = manifest.get("id") if isinstance(manifest, dict) else None
                        if not isinstance(identity, str) or not identity or not all(character.isalnum() or character in "_-" for character in identity):
                            raise ValueError(diagnostic('appearance_packs.invalid.theme.id'))
                        if identity in ("office", "slate") or (embedded() and identity in ("serpantine-night", "serpantine-day") and not isinstance(path, ResourcePath)):
                            raise ValueError(diagnostic('appearance_packs.built.in.framework.themes.cannot.be'))
                        themes[identity] = ThemeFile(identity, path, icon_key)
                except (OSError, ValueError, KeyError, TypeError, CompressionError) as error:
                    errors.append(f"{path.name}: {error}")
        return AppearanceCatalogue(request.kind, tuple(languages.values()), tuple(themes.values()), tuple(errors))


class AppearanceScanOperation:
    def __init__(self, app: AppManager, request: AppearanceScanRequest) -> None:
        self._app = app
        self._request = request

    def run(self, task_id: str, cancellation: Cancellation) -> AppearanceCatalogue:
        return self._app.get("appearance_files", AppearanceFileDriver).scan(self._request, cancellation)


class VisualResourcesOperation:
    def __init__(self, app: AppManager, request: VisualResourcesRequest) -> None:
        self._app = app
        self._request = request

    def run(self, task_id: str, cancellation: Cancellation) -> VisualResources:
        return self._app.get("appearance_files", AppearanceFileDriver).prepare(self._request, cancellation)
