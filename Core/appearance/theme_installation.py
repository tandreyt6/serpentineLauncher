from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
from zlib import error as CompressionError

from Core.configuration.settings import THEME_PACKAGE_BYTES, THEME_SCENE_BYTES
from Core.appearance.appearance_packs import AppearanceFileDriver
from Core.application.diagnostics import diagnostic
from Core.appearance.theme_scenes import scene_configuration
from universal_gui.pack.format import PackLimits, ThemePack

PROTECTED_THEMES = ('office', 'slate', 'serpantine-night', 'serpantine-day')


@dataclass(frozen=True)
class InstalledTheme:
    id: str
    path: Path
    catalogue: object
    obsolete: tuple[Path, ...]


class ThemeInstallOperation:
    def __init__(self, config, source, destination, request):
        self.config, self.source, self.destination, self.request = config, Path(source), destination, request

    def run(self, task_id, cancellation):
        if self.source.suffix.lower() != '.ugtheme' or not self.source.is_file():
            raise ValueError(diagnostic('theme.install.invalid.file'))
        self.destination.mkdir(parents=True, exist_ok=True)
        staged = None
        try:
            with self.source.open('rb') as source, NamedTemporaryFile(prefix='.theme-import-', suffix='.tmp', dir=self.destination, delete=False) as target:
                staged = Path(target.name)
                total = 0
                while True:
                    cancellation.check()
                    chunk = source.read(self.config.chunk_bytes)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > THEME_PACKAGE_BYTES:
                        raise ValueError(diagnostic('theme.install.too.large'))
                    target.write(chunk)
            limits = PackLimits(self.config.appearance_index_bytes, self.config.appearance_entry_bytes, self.config.appearance_pack_entries)
            with closing(ThemePack(staged, limits)) as pack:
                manifest = json.loads(pack.read('manifest.json'))
                if not isinstance(manifest, dict):
                    raise ValueError(diagnostic('theme.install.invalid.manifest'))
                identity = manifest.get('id')
                if not isinstance(identity, str) or not identity or len(identity) > 96 or not all(c.isalnum() or c in '_-' for c in identity):
                    raise ValueError(diagnostic('appearance_packs.invalid.theme.id'))
                if identity.casefold() in PROTECTED_THEMES:
                    raise ValueError(diagnostic('theme.install.protected'))
                if manifest.get('format') != 1 or manifest.get('api') != '0.1' or manifest.get('extends') != 'office' or not isinstance(manifest.get('tokens', {}), dict) or not isinstance(manifest.get('rules', []), list):
                    raise ValueError(diagnostic('theme.install.invalid.manifest'))
                if not pack.contains('bootloader.qml'):
                    raise ValueError(diagnostic('theme.install.missing.boot'))
                for prefix in scene_configuration(manifest):
                    if prefix and not any(key.startswith(prefix + '/') for key in pack.keys()):
                        raise ValueError(diagnostic('theme.install.empty.scenes', prefix))
                decoded = 0
                for key in pack.keys():
                    cancellation.check()
                    decoded += len(pack.read(key))
                    if decoded > THEME_SCENE_BYTES:
                        raise ValueError(diagnostic('theme.install.too.large'))
            obsolete = []
            for previous in self.destination.glob('*.ugtheme*'):
                cancellation.check()
                if previous.resolve() == self.source.resolve():
                    continue
                try:
                    with closing(ThemePack(previous, limits)) as pack:
                        if json.loads(pack.read('manifest.json')).get('id') == identity:
                            obsolete.append(previous)
                except (OSError, ValueError, KeyError, TypeError, AttributeError, CompressionError):
                    continue
            cancellation.check()
            destination = self.destination / (identity + '~' + str(time.time_ns()) + '.ugtheme')
            staged.replace(destination)
            staged = None
            catalogue = AppearanceFileDriver(self.config).scan(self.request, cancellation)
            return InstalledTheme(identity, destination, catalogue, tuple(obsolete))
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
