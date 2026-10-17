from Core.application.diagnostics import diagnostic
from dataclasses import asdict
from urllib.error import HTTPError

from Core.application.application_contracts import LocalMod
from Core.application.contracts import CoreError
from Core.content.providers.modrinth import ModrinthManager, modrinth_project
from Core.application.router import AppManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager
from Core.content.content_types import content_type


class ModInventoryManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app, self._config = app, config

    def index_path(self, build_id):
        return f'{self._config.builds_directory}/{build_id}/{self._config.build_runtime_directory}/mod-identity.json'

    def scan(self, build, selected, cancellation):
        files = self._app.get('files', FileManager)
        provider = self._app.get('modrinth', ModrinthManager)
        path = self.index_path(build.id)
        index = files.json(path) if files.exists(path) else {}
        if not isinstance(index, dict) or len(index) > self._config.mod_scan_entries:
            raise CoreError(diagnostic('mod_inventory.invalid.installed.mod.index'))
        result = []
        kinds = tuple(content_type(key) for key in dict.fromkeys(item.content_kind for item in selected))
        paths = tuple((kind, name, folder) for kind in kinds for name, folder, stamp in files.entries(f'{self._config.builds_directory}/{build.id}/{kind.directory}', recursive=True))
        for kind, name, folder in paths:
            if folder or not name.lower().endswith((kind.extension, kind.extension + '.disabled')):
                continue
            cancellation.check()
            relative = f'{self._config.builds_directory}/{build.id}/{kind.directory}/{name}'
            sha512, sha1 = files.mod_digests(relative, cancellation, self._config.mod_jar_bytes if kind.key == 'mod' else self._config.import_file_bytes)
            matching = next((item for item in selected if any(digest.value.lower() == (sha512 if digest.algorithm == 'sha512' else sha1 if digest.algorithm == 'sha1' else '') for digest in item.artifact.digests)), None)
            known = index.get(sha512)
            if matching:
                local = LocalMod(relative, sha512, sha1, matching.project_id, matching.version_id, matching.number, matching.minecraft, matching.loaders)
            elif isinstance(known, dict):
                local = LocalMod(relative, sha512, sha1, modrinth_project(known['project_id']), modrinth_project(known['version_id']), str(known.get('number', '')), tuple(known.get('minecraft', ())), tuple(known.get('loaders', ())))
            else:
                try:
                    raw = provider.read('/version_file/' + sha512 + '?algorithm=sha512', cancellation)
                except HTTPError as error:
                    if error.code != 404:
                        raise
                    raw = None
                if raw is None:
                    local = LocalMod(relative, sha512, sha1)
                else:
                    if not isinstance(raw, dict) or not any(entry.get('hashes', {}).get('sha512', '').lower() == sha512 for entry in raw.get('files', ())):
                        raise CoreError(diagnostic('mod_inventory.modrinth.hash.identification.returned.a.different'))
                    local = LocalMod(relative, sha512, sha1, modrinth_project(raw['project_id']), modrinth_project(raw['id']), str(raw.get('version_number', raw['id'])), tuple(raw.get('game_versions', ())), tuple(raw.get('loaders', ())))
            result.append(local)
        self.remember(build.id, result, cancellation)
        return tuple(result)

    def remember(self, build_id, entries, cancellation):
        files = self._app.get('files', FileManager)
        path = self.index_path(build_id)
        data = files.json(path) if files.exists(path) else {}
        data.update({entry.sha512: {key: value for key, value in asdict(entry).items() if key not in ('path', 'sha512', 'sha1')} for entry in entries if entry.project_id})
        if len(data) > self._config.mod_scan_entries:
            data = dict(tuple(data.items())[-self._config.mod_scan_entries:])
        cancellation.check()
        files.write_json(path, data)

    def record_installed(self, build_id, queue, cancellation):
        files = self._app.get('files', FileManager)
        path = self.index_path(build_id)
        data = files.json(path) if files.exists(path) else {}
        for item in queue:
            if item.artifact is not None:
                sha512, sha1 = files.mod_digests(item.artifact.relative_path, cancellation, self._config.mod_jar_bytes if item.content_kind == 'mod' else self._config.import_file_bytes)
                data[sha512] = {'project_id': item.id, 'version_id': item.version_id, 'number': item.version_number, 'minecraft': item.minecraft, 'loaders': item.loaders}
        if len(data) > self._config.mod_scan_entries:
            raise CoreError(diagnostic('mod_inventory.installed.mod.index.exceeds.limit'))
        files.write_json(path, data)
