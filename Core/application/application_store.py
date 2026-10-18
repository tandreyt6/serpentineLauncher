from Core.configuration.settings import MINIMUM_GAME_WINDOW_WIDTH, MINIMUM_GAME_WINDOW_HEIGHT, MOD_CATALOGUE_PAGE_SIZE, MODRINTH_DOWNLOAD_HOST
from Core.configuration.settings import INTERACTION_TIMING_SETTINGS, APPLICATION_SETTING_RANGES
from Core.application.diagnostics import diagnostic
import hashlib
import re

from dataclasses import asdict, fields, replace
from threading import RLock
from uuid import UUID, uuid4
from urllib.parse import urlsplit

from Core.application.application_contracts import AccountRecord, ApplicationSnapshot, BuildRecord, CoreChoice, ModQueueRecord
from Core.application.contracts import CoreError, CoreEvent
from Core.content.artifact_contracts import Artifact, Digest
from Core.installation.installation import InstallationManager
from Core.game.java import physical_memory_mb
from Core.game.metadata import object_value
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager, safe_identifier, checked_relative
from Core.content.content_types import content_type


class ApplicationStore:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self.lock = RLock()
        self.builds: dict[str, BuildRecord] = {}
        self.accounts: dict[str, AccountRecord] = {}
        self.account = ""
        self.settings = dict(config.application_settings)
        self.queue: list[ModQueueRecord] = []
        self.cores: dict[str, CoreChoice] = {}
        self.minecraft_versions: tuple[str, ...] = ()
        self.memory_limit = config.available_memory_mb or 0
        self.initialized = False

    def load(self) -> None:
        files = self._app.get("files", FileManager)
        with self.lock:
            memory_limit = self._config.available_memory_mb or physical_memory_mb()
            accounts: dict[str, AccountRecord] = {}
            account = ""
            settings = dict(self._config.application_settings)
            settings['memoryMax'] = str(max(self._config.minimum_memory_mb, memory_limit * self._config.default_java_memory_percent // 100))
            queue: list[ModQueueRecord] = []
            if files.exists(self._config.application_state_filename):
                state = object_value(files.json(self._config.application_state_filename), "application state")
                settings['firstRunComplete'] = True
                if state.get("schema", 1) != 1:
                    raise CoreError(diagnostic('application_store.unsupported.application.state.schema'))
                for raw in state.get("accounts", []):
                    item = AccountRecord(**object_value(raw, "account"))
                    if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", item.name) or len(item.uuid) != 32 or any(character not in "0123456789abcdefABCDEF" for character in item.uuid) or item.id in accounts or any(old.name.casefold() == item.name.casefold() for old in accounts.values()):
                        raise CoreError(diagnostic('application_store.invalid.or.duplicate.saved.account'))
                    accounts[item.id] = item
                account = state.get("account", "")
                if account not in accounts:
                    account = next(iter(accounts), "")
                for key, value in object_value(state.get("settings", {}), "settings").items():
                    if key in settings:
                        if type(value) is not type(settings[key]):
                            raise CoreError(diagnostic('application_store.invalid.saved.setting.type', key))
                        if key in INTERACTION_TIMING_SETTINGS:
                            minimum, maximum = APPLICATION_SETTING_RANGES[key]
                            if value.isascii() and value.isdecimal():
                                value = value.lstrip("0") or "0"
                                value = str(maximum if len(value) > len(str(maximum)) else max(minimum, min(maximum, int(value))))
                            else:
                                value = settings[key]
                        settings[key] = value
                for raw in state.get("queue", []):
                    data = dict(object_value(raw, "mod queue"))
                    if data.get('artifact') is not None:
                        artifact = object_value(data['artifact'], 'queued artifact')
                        data['artifact'] = Artifact(artifact['url'], checked_relative(artifact['relative_path']).as_posix(), artifact.get('size'), tuple(Digest(**object_value(digest, 'digest')) for digest in artifact.get('digests', ())))
                    data['required_by'] = tuple(data.get('required_by', ()))
                    data['required_project_ids'] = tuple(data.get('required_project_ids', ()))
                    data['minecraft'] = tuple(data.get('minecraft', ()))
                    data['loaders'] = tuple(data.get('loaders', ()))
                    data['replacements'] = tuple(tuple(pair) for pair in data.get('replacements', ()))
                    item = ModQueueRecord(**{**data, "state": "queued"})
                    if any(not isinstance(value, str) or not value for value in (item.id, item.title, item.source, item.owner_id)):
                        raise CoreError(diagnostic('application_store.invalid.saved.mod.queue.entry'))
                    if not isinstance(item.version_id, str) or not isinstance(item.version_number, str):
                        raise CoreError(diagnostic('application_store.invalid.saved.mod.version'))
                    kind = content_type(item.content_kind)
                    prefix = f'{self._config.builds_directory}/{safe_identifier(item.owner_id)}/{kind.directory}/'
                    if item.artifact is not None and (not item.artifact.relative_path.startswith(prefix) or not item.artifact.relative_path.lower().endswith(kind.extension)):
                        raise CoreError(diagnostic('application_store.queued.mod.artifact.escapes.its.build'))
                    if item.artifact is not None:
                        url = urlsplit(item.artifact.url)
                        if url.scheme != 'https' or url.hostname != MODRINTH_DOWNLOAD_HOST or url.username or url.password or url.port not in (None, 443) or url.fragment or type(item.artifact.size) is not int or not 0 <= item.artifact.size <= (self._config.mod_jar_bytes if kind.key == 'mod' else self._config.import_file_bytes) or not item.artifact.digests or any(digest.algorithm not in ('sha1', 'sha512') or not re.fullmatch('[0-9a-fA-F]{' + ('40' if digest.algorithm == 'sha1' else '128') + '}', digest.value) for digest in item.artifact.digests):
                            raise CoreError(diagnostic('application_store.invalid.saved.mod.artifact'))
                    if item.queue_id and not re.fullmatch('[0-9a-f]{32}', item.queue_id):
                        raise CoreError(diagnostic('application_store.invalid.saved.queue.id'))
                    if any(len(pair) != 2 or not isinstance(pair[0], str) or not checked_relative(pair[0]).as_posix().startswith(prefix) or not pair[0].lower().endswith((kind.extension, kind.extension + '.disabled')) or not isinstance(pair[1], str) or not re.fullmatch('[0-9a-f]{128}', pair[1]) for pair in item.replacements):
                        raise CoreError(diagnostic('application_store.invalid.mod.replacement.paths'))
                    if not any(old.owner_id == item.owner_id and (old.queue_id or old.id) == (item.queue_id or item.id) for old in queue):
                        queue.append(item)
            builds: dict[str, BuildRecord] = {}
            allowed = {field.name for field in fields(BuildRecord)}
            files.ensure_directory(self._config.builds_directory)
            for name, folder, _ in files.entries(self._config.builds_directory):
                marker = f"{self._config.builds_directory}/{name}/{self._config.build_metadata_filename}"
                if not folder or not files.exists(marker):
                    continue
                value = object_value(files.json(marker), "build metadata")
                build = BuildRecord(**{key: entry for key, entry in value.items() if key in allowed})
                self.validate_build(build)
                if build.id != name or any(key.casefold() == build.id.casefold() for key in builds):
                    raise CoreError(diagnostic('application_store.build.ids.must.match.directory.names'))
                builds[build.id] = build
            cores = self._installed_cores({})
            self.memory_limit = memory_limit
            self.accounts, self.account, self.settings = accounts, account, settings
            self.builds = builds
            self.queue = [item for item in queue if item.owner_id in builds]
            self.cores = cores
            self.minecraft_versions = ()
            self.initialized = True
            self.publish()

    def scan_cores(self) -> None:
        with self.lock:
            self.cores = self._installed_cores(self.cores)

    def _installed_cores(self, existing: dict[str, CoreChoice]) -> dict[str, CoreChoice]:
        files = self._app.get("files", FileManager)
        cores = {key: replace(item, installed=False) for key, item in existing.items()}
        for name, folder, _ in files.entries(self._config.cores_directory):
            if not folder or not files.exists(f"{self._config.cores_directory}/{name}/{self._config.install_metadata_filename}"):
                continue
            receipt = self._app.get("installation", InstallationManager).receipt(name)
            ready = self._app.get("installation", InstallationManager).ready(name)
            cores[name] = CoreChoice(name, receipt.minecraft_version, receipt.loader, receipt.loader_version, ready)
        return cores

    def save(self) -> None:
        self.persist()

    def persist(self, accounts: dict[str, AccountRecord] | None = None, account: str | None = None, settings: dict[str, str | bool] | None = None, queue: list[ModQueueRecord] | None = None) -> None:
        with self.lock:
            next_accounts = self.accounts if accounts is None else accounts
            next_account = self.account if account is None else account
            next_settings = self.settings if settings is None else settings
            next_queue = self.queue if queue is None else queue
            self._app.get("files", FileManager).write_json(self._config.application_state_filename, {"schema": 1, "accounts": [asdict(item) for item in next_accounts.values()], "account": next_account, "settings": next_settings, "queue": [asdict(item) for item in next_queue]})
            self.accounts, self.account, self.settings, self.queue = next_accounts, next_account, next_settings, next_queue

    def snapshot(self) -> ApplicationSnapshot:
        with self.lock:
            return ApplicationSnapshot(tuple(self.builds.values()), tuple(self.accounts.values()), self.account, tuple(self.settings.items()), tuple(self.queue), tuple(sorted(self.cores.values(), key=self._core_sort)), self.minecraft_versions, self.memory_limit)

    @staticmethod
    def _core_sort(core: CoreChoice) -> tuple[bool, str, str, str]:
        return not core.installed, core.loader, core.minecraft, core.version

    def publish(self) -> None:
        self._app.get("events", EventManager).publish(CoreEvent("application", self.snapshot()))

    def write_build(self, build: BuildRecord, create: bool = False) -> None:
        self.validate_build(build)
        files = self._app.get("files", FileManager)
        with self.lock:
            if not create and build.id not in self.builds:
                raise CoreError(diagnostic('application_store.unknown.build'))
            if create and (any(key.casefold() == build.id.casefold() for key in self.builds) or files.exists(f"{self._config.builds_directory}/{build.id}") or files.is_directory(f"{self._config.builds_directory}/{build.id}")):
                raise CoreError(diagnostic('application_store.build.id.or.directory.already.exists'))
            files.write_json(f"{self._config.builds_directory}/{build.id}/{self._config.build_metadata_filename}", asdict(build))
            self.builds[build.id] = build
            self.publish()

    @staticmethod
    def validate_build(build: BuildRecord) -> None:
        safe_identifier(build.id)
        if not isinstance(build.title_color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", build.title_color):
            raise CoreError(diagnostic('application_store.invalid.build.title.color'))
        if any(not isinstance(value, str) for value in (build.title, build.minecraft, build.loader, build.loader_version, build.description, build.description_format, build.background, build.java_path, build.jvm_args)) or not build.title.strip() or not build.minecraft or build.description_format not in ("md", "html") or build.loader not in ("Vanilla", "Fabric", "Quilt", "Forge", "NeoForge"):
            raise CoreError(diagnostic('application_store.invalid.build.metadata'))
        if build.loader != "Vanilla" and not build.loader_version:
            raise CoreError(diagnostic('application_store.loader.version.is.required'))
        if any(value is not None and (type(value) is not int or value < 1) for value in (build.memory_min, build.memory_max, build.width, build.height)) or type(build.fullscreen) is not bool:
            raise CoreError(diagnostic('application_store.invalid.build.runtime.settings'))
        if (build.width is None) != (build.height is None) or build.width is not None and (build.width < MINIMUM_GAME_WINDOW_WIDTH or build.height < MINIMUM_GAME_WINDOW_HEIGHT):
            raise CoreError(diagnostic('application_store.invalid.window.dimensions'))

    def add_account(self, name: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", name):
            raise CoreError(diagnostic('application_store.offline.username.must.contain.letters.digits'))
        identifier = str(UUID(bytes=hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest(), version=3))
        account_uuid = identifier.replace("-", "")
        with self.lock:
            if any(item.name.casefold() == name.casefold() for item in self.accounts.values()):
                raise CoreError(diagnostic('application_store.account.already.exists'))
            while identifier in self.accounts:
                identifier = str(uuid4())
            accounts = {**self.accounts, identifier: AccountRecord(identifier, name, account_uuid)}
            self.persist(accounts=accounts, account=identifier)
            self.publish()

    def rename_account(self, identifier: str, name: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", name):
            raise CoreError(diagnostic('application_store.offline.username.must.contain.letters.digits'))
        with self.lock:
            if identifier not in self.accounts:
                raise CoreError(diagnostic('application_store.unknown.account'))
            if any(item.id != identifier and item.name.casefold() == name.casefold() for item in self.accounts.values()):
                raise CoreError(diagnostic('application_store.account.already.exists'))
            account_uuid = UUID(bytes=hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest(), version=3).hex
            accounts = {**self.accounts, identifier: replace(self.accounts[identifier], name=name, uuid=account_uuid)}
            self.persist(accounts=accounts)
            self.publish()
