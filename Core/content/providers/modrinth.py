from Core.configuration.settings import MOD_CATALOGUE_MAXIMUM_PAGE_SIZE, MOD_SEARCH_QUERY_LENGTH, MOD_DESCRIPTION_LENGTH, MOD_AUTHOR_LENGTH, MODRINTH_PROJECT_HOSTS, MODRINTH_DOWNLOAD_HOST
from Core.application.diagnostics import diagnostic
from Core.configuration.settings import MODRINTH_PROJECT_URL
import json
import re
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from PIL import Image

from urllib.parse import quote, urlencode, urlsplit

from Core.application.application_contracts import BuildRecord, ModCatalogEntry, ModSearchRequest, ModSearchResult, ModProjectResult, ModVersionEntry, ModIconResult, ModFiltersResult, ResolvedMod
from Core.application.contracts import Artifact, CoreError, CoreEvent, Digest, HttpRequest
from Core.game.metadata import object_value, string_value
from Core.network.network import NetworkManager
from Core.application.router import AppManager, EventManager, AccessManager
from Core.application.settings import CoreConfig
from Core.application.storage import checked_relative, FileManager
from Core.application.tasks import Cancellation
from Core.content.content_types import content_type


def modrinth_project(source: str, content_kind: str = 'mod') -> str:
    content_type(content_kind)
    parsed = urlsplit(source)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or parsed.hostname not in MODRINTH_PROJECT_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.query or parsed.fragment:
            raise CoreError(diagnostic('modrinth.invalid.modrinth.project.link'))
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != content_kind:
            raise CoreError("Modrinth link must refer to a " + content_kind + " project")
        project = parts[1]
    else:
        project = source
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project):
        raise CoreError(diagnostic('modrinth.invalid.modrinth.project.id.or.slug'))
    return project


class ModrinthManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._categories = None

    def read(self, path: str, cancellation: Cancellation) -> object:
        data = self._app.get("network", NetworkManager).read(HttpRequest(self._config.modrinth_api_url.rstrip("/") + path), cancellation, self._config.maximum_metadata_bytes)
        return json.loads(data)

    def search(self, build: BuildRecord, query: str, cancellation: Cancellation, request: ModSearchRequest | None = None) -> ModSearchResult:
        request = request or ModSearchRequest(build.id, "", query)
        if request.build_id != build.id or type(request.offset) is not int or request.offset < 0 or type(request.limit) is not int or not 1 <= request.limit <= MOD_CATALOGUE_MAXIMUM_PAGE_SIZE or len(request.query) > MOD_SEARCH_QUERY_LENGTH:
            raise CoreError(diagnostic('modrinth.invalid.mod.search.request'))
        kind = content_type(request.content_kind)
        if kind.key == 'mod' and build.loader == "Vanilla":
            raise CoreError(diagnostic('modrinth.vanilla.builds.do.not.support.mods'))
        facets = [["project_type:" + kind.key]]
        if request.loader:
            if request.loader not in kind.loaders:
                raise CoreError(diagnostic('modrinth.unknown.mod.loader.filter'))
            facets.append(['categories:' + request.loader])
        if request.minecraft:
            if len(request.minecraft) > 100:
                raise CoreError(diagnostic('modrinth.invalid.minecraft.version.filter'))
            facets.append(['versions:' + request.minecraft])
        if request.category:
            if not re.fullmatch(r"[a-z0-9_-]+", request.category):
                raise CoreError(diagnostic('modrinth.invalid.mod.category'))
            facets.append(["categories:" + request.category])
        sort = request.sort or ("relevance" if request.query else "downloads")
        if sort not in ("relevance", "downloads", "follows", "newest", "updated"):
            raise CoreError(diagnostic('modrinth.invalid.mod.catalogue.sorting'))
        data = object_value(self.read("/search?" + urlencode({"query": request.query, "facets": json.dumps(facets), "limit": request.limit, "offset": request.offset, "index": sort}), cancellation), "Modrinth search")
        hits = data.get("hits")
        total = data.get("total_hits")
        if not isinstance(hits, list) or len(hits) > request.limit or type(total) is not int or total < 0:
            raise CoreError(diagnostic('modrinth.invalid.modrinth.search.response'))
        mods = []
        for raw in hits:
            item = object_value(raw, "Modrinth hit")
            project = modrinth_project(string_value(item["project_id"], "project ID"))
            mods.append(ModCatalogEntry(project, string_value(item["title"], "mod title"), MODRINTH_PROJECT_URL + "/" + kind.key + "/" + project, build.id, str(item.get("description", ""))[:MOD_DESCRIPTION_LENGTH], str(item.get("author", ""))[:MOD_AUTHOR_LENGTH], max(0, int(item.get("downloads", 0))), str(item.get("icon_url") or "")))
        next_offset = request.offset + len(hits)
        result = ModSearchResult(build.id, tuple(mods), request.request_id, request.offset, next_offset, bool(hits) and next_offset < total, kind.key)
        self._app.get("events", EventManager).publish(CoreEvent("mod_search", result))
        return result

    def project(self, build, source, request_id, cancellation, content_kind='mod'):
        content_type(content_kind)
        project = object_value(self.read('/project/' + quote(modrinth_project(source, content_kind), safe=''), cancellation), 'mod project')
        if project.get('project_type', content_kind) != content_kind:
            raise CoreError(diagnostic('modrinth.project.belongs.to.another.content.type'))
        project_id = modrinth_project(string_value(project['id'], 'mod project ID'))
        parameters = urlencode({'include_changelog': 'false'})
        raw = self.read('/project/' + project_id + '/version?' + parameters, cancellation)
        if not isinstance(raw, list):
            raise CoreError(diagnostic('modrinth.invalid.mod.version.list'))
        versions = []
        for version in sorted(raw, key=lambda entry: str(entry.get('date_published', '')), reverse=True):
            if version.get('project_id') != project_id:
                continue
            artifact = self._artifact(build, version, content_kind)
            versions.append(ModVersionEntry(modrinth_project(version['id']), str(version.get('version_number', version['id'])), str(version.get('name', version['id'])), str(version.get('version_type', 'release')), str(version.get('date_published', '')), artifact.relative_path.rsplit('/', 1)[-1], artifact.size, tuple(version.get('game_versions', ())), tuple(version.get('loaders', ()))))
        result = ModProjectResult(build.id, request_id, project_id, string_value(project['title'], 'mod title'), str(project.get('description', '')), str(project.get('body', '')), str(project.get('icon_url') or ''), tuple(versions), content_kind)
        self._app.get('events', EventManager).publish(CoreEvent('mod_project', result))
        return result

    def selected_version(self, build, project, version_id, cancellation):
        version = object_value(self.read('/version/' + quote(modrinth_project(version_id), safe=''), cancellation), 'mod version')
        if version.get('project_id') != project:
            raise CoreError(diagnostic('modrinth.selected.mod.version.belongs.to.another'))
        self._artifact(build, version)
        return str(version.get('version_number', version_id))

    def plan(self, build, project, version_id, title, cancellation, content_kind='mod'):
        content_type(content_kind)
        pending = [(project, version_id, "", True, build.minecraft, build.loader.lower() if content_kind == 'mod' else '', content_kind, '')]
        resolved, parents, titles = {}, {}, {project: title}
        parent_ids = {}
        project_kinds = {project: content_kind}
        versions = {}
        while pending:
            cancellation.check()
            project_id, requested, parent, exact, minecraft, loader, item_kind, parent_id = pending.pop()
            if project_id and parent:
                if project_id not in project_kinds:
                    data = object_value(self.read('/project/' + quote(modrinth_project(project_id), safe=''), cancellation), 'dependency project')
                    project_kinds[project_id] = data.get('project_type', item_kind)
                    titles[project_id] = string_value(data['title'], 'dependency title')
                dependency_kind = project_kinds[project_id]
                content_type(dependency_kind)
                if dependency_kind != item_kind:
                    loader = build.loader.lower() if dependency_kind == 'mod' else ''
                item_kind = dependency_kind
            identity = (project_id, requested)
            if identity in versions:
                version = versions[identity]
            elif requested:
                version = object_value(self.read('/version/' + quote(modrinth_project(requested), safe=''), cancellation), 'mod version')
            else:
                raw = self.read('/project/' + quote(modrinth_project(project_id), safe='') + '/version?include_changelog=false', cancellation)
                if not isinstance(raw, list) or not raw:
                    raise CoreError('No published dependency version for ' + project_id)
                candidates = [object_value(item, 'mod version') for item in raw]
                compatible = [item for item in candidates if minecraft in item.get('game_versions', ()) and (not loader or loader in item.get('loaders', ()))]
                version = sorted(compatible or candidates, key=self._version_sort, reverse=True)[0]
            versions[identity] = version
            canonical = modrinth_project(version['project_id'])
            if project_id and requested and canonical != project_id:
                raise CoreError(diagnostic('modrinth.selected.dependency.version.belongs.to.another'))
            selected = modrinth_project(version['id'])
            key = (canonical, selected)
            if parent:
                parents.setdefault(key, set()).add(parent)
                parent_ids.setdefault(key, set()).add(parent_id)
            if key in resolved:
                if exact and not resolved[key].exact:
                    resolved[key] = replace(resolved[key], exact=True)
                continue
            if len(resolved) >= self._config.mod_records:
                raise CoreError(diagnostic('modrinth.mod.dependency.graph.exceeds.limit'))
            if not titles.get(canonical):
                data = object_value(self.read('/project/' + canonical, cancellation), 'mod project')
                titles[canonical] = string_value(data['title'], 'dependency title')
                item_kind = data.get('project_type', item_kind)
            name = titles[canonical] or canonical
            artifact = self._artifact(build, version, item_kind)
            resolved[key] = ResolvedMod(canonical, selected, name, str(version.get('version_number', selected)), artifact, exact=exact, minecraft=tuple(version.get('game_versions', ())), loaders=tuple(version.get('loaders', ())), content_kind=item_kind)
            games, loaders = version.get('game_versions', ()), version.get('loaders', ())
            game = build.minecraft if build.minecraft in games else next(iter(games), build.minecraft)
            family = build.loader.lower() if build.loader.lower() in loaders else next(iter(loaders), build.loader.lower())
            for dependency in version.get('dependencies', ()):
                kind = dependency.get('dependency_type')
                if kind == 'required':
                    dependency_project, pin = dependency.get('project_id') or '', dependency.get('version_id') or ''
                    if not dependency_project and not pin:
                        raise CoreError('Required external mod dependency cannot be resolved: ' + str(dependency.get('file_name', name)))
                    pending.append((dependency_project, pin, name, bool(pin), game, family, item_kind, canonical))
                elif kind not in ('optional', 'embedded', 'incompatible'):
                    raise CoreError(diagnostic('modrinth.unknown.modrinth.dependency.type'))
        return tuple(replace(item, required_by=tuple(sorted(parents.get(key, ()))) if index else (), required_project_ids=tuple(sorted(parent_ids.get(key, ()))) if index else ()) for index, (key, item) in enumerate(resolved.items()))

    def filters(self, build_id, cancellation, content_kind='mod'):
        content_type(content_kind)
        with self._app.get('access', AccessManager).access('modrinth-categories', cancellation):
            if self._categories is None:
                raw = self.read('/tag/category', cancellation)
                if not isinstance(raw, list):
                    raise CoreError(diagnostic('modrinth.invalid.mod.category.list'))
                self._categories = tuple((item['project_type'], item['name']) for item in raw if isinstance(item, dict) and item.get('project_type') in ('mod', 'resourcepack', 'shader') and re.fullmatch(r'[a-z0-9_-]+', item.get('name', '')))
            result = ModFiltersResult(build_id, tuple(sorted({name for kind, name in self._categories if kind == content_kind})), content_kind)
        self._app.get('events', EventManager).publish(CoreEvent('mod_filters', result))
        return result

    def icons(self, entries, cancellation):
        if not isinstance(entries, list) or len(entries) > 100:
            raise CoreError(diagnostic('modrinth.invalid.mod.icon.request'))
        files = self._app.get('files', FileManager)
        for item in entries:
            cancellation.check()
            project = modrinth_project(item['id'])
            url = item['url']
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname != MODRINTH_DOWNLOAD_HOST or parsed.username or parsed.password or parsed.port not in (None, 443):
                continue
            destination = f'{self._config.cache_directory}/modrinth-icons/{sha256(url.encode()).hexdigest()}.png'
            try:
                with self._app.get('access', AccessManager).access('mod-icon:' + destination, cancellation):
                    if not files.exists(destination):
                        data = self._app.get('network', NetworkManager).read(HttpRequest(url), cancellation, self._config.mod_icon_bytes)
                        with Image.open(BytesIO(data)) as image:
                            if max(image.size) > self._config.mod_icon_dimension or image.width * image.height > self._config.mod_icon_pixels:
                                raise CoreError(diagnostic('modrinth.mod.icon.exceeds.image.limits'))
                            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
                            output = BytesIO()
                            image.convert('RGBA').save(output, format='PNG')
                        files.write_bytes(destination, output.getvalue(), cancellation)
                self._app.get('events', EventManager).publish(CoreEvent('mod_icon', ModIconResult(project, str(files.path(destination)))))
            except (OSError, ValueError, CoreError, Image.DecompressionBombError) as error:
                cancellation.check()
                self._app.log('Mod icon unavailable: ' + str(error), 'DEBUG')

    def resolve(self, build: BuildRecord, source: str, cancellation: Cancellation, requested_projects: tuple[str, ...] = ()) -> tuple[Artifact, ...]:
        return self.resolve_sources(build, (source,), cancellation, requested_projects)

    def resolve_sources(self, build: BuildRecord, sources: tuple[str, ...], cancellation: Cancellation, requested_projects: tuple[str, ...] = (), pinned_versions: tuple[tuple[str, str], ...] = ()) -> tuple[Artifact, ...]:
        if build.loader == "Vanilla":
            raise CoreError(diagnostic('modrinth.vanilla.builds.do.not.support.mods'))
        parameters = urlencode({"include_changelog": "false"})
        pins = dict(pinned_versions)
        pending = [(modrinth_project(source), pins.get(modrinth_project(source), "")) for source in sources]
        visited = set()
        artifacts = {}
        while pending:
            cancellation.check()
            project_id, version_id = pending.pop()
            identity = ("version", version_id) if version_id else ("project", project_id)
            if identity in visited:
                continue
            visited.add(identity)
            if len(visited) > self._config.mod_records:
                raise CoreError(diagnostic('modrinth.mod.dependency.graph.exceeds.limit'))
            if version_id:
                version = object_value(self.read("/version/" + quote(version_id, safe=""), cancellation), "mod version")
            else:
                versions = self.read("/project/" + quote(project_id, safe="") + "/version?" + parameters, cancellation)
                if not isinstance(versions, list) or not versions:
                    raise CoreError(diagnostic('modrinth.no.published.version.for.mod', project_id))
                releases = [object_value(item, "mod version") for item in versions]
                releases.sort(key=self._version_sort, reverse=True)
                version = releases[0]
            if version_id and project_id and version.get("project_id") != project_id:
                raise CoreError(diagnostic('modrinth.pinned.mod.version.belongs.to.a'))
            artifact = self._artifact(build, version)
            name = artifact.relative_path.rsplit("/", 1)[-1]
            previous = artifacts.get(name.casefold())
            if previous is not None and previous != artifact:
                raise CoreError(diagnostic('modrinth.mod.dependencies.contain.conflicting.filenames'))
            artifacts[name.casefold()] = artifact
            for dependency in version.get("dependencies", []):
                if dependency["dependency_type"] == "required":
                    if not dependency.get("version_id") and not dependency.get("project_id"):
                        raise CoreError(diagnostic('modrinth.required.external.mod.dependency.cannot.be'))
                    dependency_project = dependency.get('project_id') or ''
                    pending.append((dependency_project, pins.get(dependency_project) or dependency.get('version_id') or ''))
                elif dependency["dependency_type"] == "incompatible":
                    pass
                elif dependency["dependency_type"] not in ("optional", "embedded"):
                    raise CoreError(diagnostic('modrinth.unknown.modrinth.dependency.type'))
        return tuple(artifacts.values())


    def _artifact(self, build, version, content_kind='mod'):
        kind = content_type(content_kind)
        files = version["files"]
        entry = next((item for item in files if item.get("primary")), files[0] if files else None)
        if entry is None:
            raise CoreError(diagnostic('modrinth.mod.version.has.no.file'))
        name = string_value(entry["filename"], "mod filename")
        checked_relative(name)
        if "/" in name or not name.lower().endswith(kind.extension):
            raise CoreError("Content download must be a single " + kind.extension + " filename")
        url = string_value(entry["url"], "mod URL")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != MODRINTH_DOWNLOAD_HOST or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment:
            raise CoreError(diagnostic('modrinth.mod.file.url.is.outside.modrinth'))
        hashes = object_value(entry["hashes"], "mod hashes")
        digests = tuple(Digest(algorithm, hashes[algorithm]) for algorithm in ("sha512", "sha1") if algorithm in hashes)
        if not digests:
            raise CoreError(diagnostic('modrinth.mod.download.has.no.integrity.hash'))
        for digest in digests:
            length = 128 if digest.algorithm == "sha512" else 40
            if not isinstance(digest.value, str) or len(digest.value) != length or any(character not in "0123456789abcdefABCDEF" for character in digest.value):
                raise CoreError(diagnostic('modrinth.mod.download.has.an.invalid.integrity'))
        if type(entry["size"]) is not int or entry["size"] < 0 or entry["size"] > (self._config.mod_jar_bytes if kind.key == 'mod' else self._config.import_file_bytes):
            raise CoreError(diagnostic('modrinth.mod.file.size.is.invalid.or'))
        artifact = Artifact(url, f"{self._config.builds_directory}/{build.id}/{kind.directory}/{name}", entry["size"], digests)
        return artifact

    @staticmethod
    def _version_sort(version: dict) -> tuple[bool, str]:
        return version.get("version_type", "release") == "release", version.get("date_published", "")
