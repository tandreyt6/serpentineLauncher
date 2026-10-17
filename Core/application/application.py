from Core.configuration.settings import MINIMUM_GAME_WINDOW_WIDTH, MINIMUM_GAME_WINDOW_HEIGHT, MOD_CATALOGUE_PAGE_SIZE, MODRINTH_DOWNLOAD_HOST
from Core.application.diagnostics import diagnostic
import json
import re
import shlex

from dataclasses import replace
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from threading import RLock
from urllib.parse import unquote, urlsplit

from Core.configuration.settings import APPLICATION_SETTING_CHOICES, APPLICATION_SETTING_RANGES

from Core.application.application_contracts import ApplicationCommand, BackendResult, BuildRecord, CoreBrowseRequest, CoreChoice, ModQueueRecord, ModSearchRequest
from Core.application.application_store import ApplicationStore
from Core.content.catalogue import CatalogueManager
from Core.application.contracts import AccountSession, Artifact, CoreError, CoreEvent, CoreInstallation, DownloadBatch, InstalledCore, InstallRequest, JavaOverrides, JavaSettings, LaunchRequest, TaskStage
from Core.network.downloads import DownloadManager
from Core.content.editor_files import EditorFilesManager
from Core.installation.installation import InstallationManager, MetadataManager, core_identifier
from Core.game.java import JavaManager, select_java_runtime
from Core.game.launch import LaunchManager
from Core.application.logging_manager import LogManager
from Core.content.providers.modrinth import ModrinthManager, modrinth_project
from Core.content.mods.mod_queue import ModQueueManager
from Core.content.mods.mod_imports import ModImportManager
from Core.application.router import AccessManager, AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager, checked_relative, safe_identifier
from Core.application.tasks import Cancellation, TaskManager
from Core.application.first_run import prepare_first_run


def parse_jvm_arguments(value: str) -> tuple[str, ...]:
    arguments = tuple(item[1:-1] if len(item) >= 2 and item[0] == item[-1] and item[0] in ("'", '"') else item for item in shlex.split(value, posix=False))
    if any(argument.startswith(("-Xmx", "-Xms")) or argument in ("-cp", "-classpath", "--class-path", "-jar") for argument in arguments):
        raise CoreError(diagnostic('application.memory.and.classpath.must.use.dedicated'))
    return arguments


class ApplicationManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._lock = RLock()
        self._task_links: dict[tuple[str, str], BackendResult] = {}
        self._app.get("events", EventManager).subscribe("core.queued", self._queued_core, deferred=False)
        self._app.get("events", EventManager).subscribe("core.installed", self._installed_core, deferred=False)

    def _installed_core(self, event: CoreEvent) -> None:
        receipt = event.payload
        if not isinstance(receipt, InstalledCore):
            return
        store = self._app.get("application_store", ApplicationStore)
        with store.lock:
            store.cores[receipt.core_id] = CoreChoice(receipt.core_id, receipt.minecraft_version, receipt.loader, receipt.loader_version, True)
            store.publish()

    def _queued_core(self, event: CoreEvent) -> None:
        installation = event.payload
        if not isinstance(installation, CoreInstallation):
            return
        store = self._app.get("application_store", ApplicationStore)
        with store.lock:
            store.cores[installation.core_id] = CoreChoice(installation.core_id, installation.minecraft_version, installation.loader, installation.loader_version)
            store.publish()
        result = BackendResult("task.core", installation.core_id, installation.task_id)
        self.link(result)
        self._app.get("events", EventManager).publish(CoreEvent("backend", result))

    def link(self, result: BackendResult) -> None:
        if result.action not in ("task.core", "task.mod", "task.resources"):
            raise CoreError(diagnostic('application.only.resource.task.links.can.be'))
        with self._lock:
            self._task_links[(result.action, result.key)] = result

    def task_links(self) -> tuple[BackendResult, ...]:
        with self._lock:
            return tuple(self._task_links.values())

    @contextmanager
    def access(self, resource: str, cancellation: Cancellation) -> Iterator[None]:
        with self._app.get("access", AccessManager).access("application:" + resource, cancellation):
            yield

    def submit(self, command: ApplicationCommand) -> str:
        stages = tuple(TaskStage(key) for key in ("metadata", "download", "finalize")) if command.action in ("sync_mods", "sync_and_play") else ()
        queue = 'files' if command.action in ('editor_scan', 'read_file') else 'background'
        return self._app.get("tasks", TaskManager).submit(command.action, ApplicationOperation(self._app, command).run, stages=stages, queue=queue, retryable=command.action in ('sync_mods', 'sync_and_play'))

    def close(self) -> None:
        self._app.get("events", EventManager).unsubscribe("core.queued", self._queued_core)
        self._app.get("events", EventManager).unsubscribe("core.installed", self._installed_core)


class ApplicationOperation:
    def __init__(self, app: AppManager, command: ApplicationCommand) -> None:
        self._app = app
        self._command = command

    def result(self, action: str, key: str = "", text: str = "", path: str = "") -> None:
        result = BackendResult(action, key, text, path)
        if action in ("task.core", "task.mod", "task.resources"):
            self._app.get("application", ApplicationManager).link(result)
        self._app.get("events", EventManager).publish(CoreEvent("backend", result))

    def guard(self, key: str, hot_paths: tuple[str, ...] = ()) -> None:
        store = self._app.get("application_store", ApplicationStore)
        clients = self._app.get("launch", LaunchManager).snapshots()
        if store.settings.get("safeMode", True) and any(client.build_id.casefold() == key.casefold() and client.state in ("starting", "running", "closing") for client in clients):
            if hot_paths and all(len(path.parts) > 1 and path.parts[0].casefold() in ("resourcepacks", "shaderpacks") for path in map(checked_relative, hot_paths)):
                return
            raise CoreError(diagnostic('application.build.is.running.close.it.before'))

    def guard_content_queue(self, key, queue):
        config = self._app.get("config", CoreConfig)
        prefix = f"{config.builds_directory}/{key}/"
        paths = []
        for item in queue:
            if item.content_kind not in ('resourcepack', 'shader') or item.artifact is None:
                return self.guard(key)
            for path in (item.artifact.relative_path, *(path for path, _ in item.replacements)):
                if not path.startswith(prefix):
                    return self.guard(key)
                paths.append(path.removeprefix(prefix))
        self.guard(key, tuple(paths))

    def run(self, task_id: str, cancellation: Cancellation) -> object:
        action = self._command.action
        if action != "bootstrap":
            self._app.get("logs", LogManager).write(action + " " + self._command.key)
        manager = self._app.get("application", ApplicationManager)
        if action == "bootstrap":
            with manager.access("bootstrap", cancellation):
                store = self._app.get("application_store", ApplicationStore)
                if store.initialized:
                    self._app.get("catalogue", CatalogueManager).initialize()
                    store.publish()
                    self.prepare_resources()
                    return store.snapshot()
                return self.run_command(task_id, cancellation)
        if action in ("delete_core", "download"):
            with manager.access("core:" + self._command.key, cancellation):
                return self.run_command(task_id, cancellation)
        protected = ("create", "decorate", "build_settings", "update_build", "delete", "play", "install_build", "sync_and_play", "sync_mods", "save_file", "drop_mod", "import_files", "toggle_mod", "delete_file", "add_mod", "remove_queued_mod", "resolve_mod_queue")
        if action in protected:
            with manager.access("build:" + self._command.key, cancellation):
                if action in ("play", "install_build"):
                    store = self._app.get("application_store", ApplicationStore)
                    with store.lock:
                        build = store.builds.get(self._command.key)
                    if build is None:
                        raise CoreError(diagnostic('application.unknown.build'))
                    core_id = core_identifier(InstallRequest(build.minecraft, build.loader, build.loader_version))
                    with manager.access("core:" + core_id, cancellation):
                        return self.run_command(task_id, cancellation)
                return self.run_command(task_id, cancellation)
        return self.run_command(task_id, cancellation)

    def run_command(self, task_id: str, cancellation: Cancellation) -> object:
        store = self._app.get("application_store", ApplicationStore)
        files = self._app.get("files", FileManager)
        config = self._app.get("config", CoreConfig)
        command = self._command
        action, key, value = command.action, command.key, command.value
        fields = dict(command.fields)
        cancellation.check()
        if action == "prepare_first_run":
            return prepare_first_run(self._app, cancellation)
        if action == "browse_cores":
            tasks = self._app.get("tasks", TaskManager)
            active_tasks = {task.task_id for task in tasks.snapshots() if task.state in ("queued", "running", "retrying", "paused", "cancelling")}
            active = tuple(link.key for link in self._app.get("application", ApplicationManager).task_links() if link.action == "task.core" and link.text in active_tasks)
            request = CoreBrowseRequest(fields["request_id"], fields.get("state", "all"), key, value, int(fields.get("offset", "0")), int(fields.get("limit", str(config.core_catalogue_page_size))))
            result = self._app.get("catalogue", CatalogueManager).browse(request, active, cancellation)
            self._app.get("events", EventManager).publish(CoreEvent("core.browse", result))
            return result
        if action in ("decorate", "build_settings", "update_build", "delete", "play", "install_build", "sync_and_play", "editor_scan", "read_file", "save_file", "mod_search", "mod_project", "mod_icons", "mod_filters", "add_mod", "remove_queued_mod", "sync_mods", "drop_mod", "import_files", "toggle_mod", "delete_file", "open_build_folder"):
            with store.lock:
                if key not in store.builds:
                    raise CoreError(diagnostic('application.unknown.build'))
        if action == "bootstrap":
            self._app.get("installation", InstallationManager).migrate(cancellation)
            store.load()
            logs = self._app.get("logs", LogManager)
            logs.configure(str(store.settings.get("logMode", "normal")), int(store.settings.get("zipBatch", "5")))
            logs.write("Launcher initialized")
            store.publish()
            self._app.get("catalogue", CatalogueManager).initialize()
            self.prepare_resources()
            return store.snapshot()
        if action == "update_catalogue":
            return self._app.get("catalogue", CatalogueManager).request_update()
        if action == "catalogue":
            catalogue = self._app.get("catalogue", CatalogueManager).versions(key or "Vanilla", value)
            self._app.get("events", EventManager).publish(CoreEvent("core.versions", catalogue))
            return catalogue.cores
        if action == "create":
            build = BuildRecord(key, fields["title"], fields["minecraft"], fields["loader"], fields.get("loader_version", ""))
            store.write_build(build, create=True)
            self.result("created", key)
            request = InstallRequest(build.minecraft, build.loader, build.loader_version, Path(store.settings["javaPath"]) if store.settings.get("javaPath") else None)
            core_id = core_identifier(request)
            with store.lock:
                store.cores.setdefault(core_id, CoreChoice(core_id, build.minecraft, build.loader, build.loader_version))
                store.publish()
            with self._app.get("application", ApplicationManager).access("core:" + core_id, cancellation):
                if not self._app.get("installation", InstallationManager).ready(core_id):
                    task = self.install(request)
                    self.result("task.core", core_id, task)
            return build
        if action in ("add_account", "rename_account", "account", "delete_account"):
            if action == "add_account":
                store.add_account(value)
            elif action == "rename_account":
                store.rename_account(key, value)
            else:
                with store.lock:
                    if key not in store.accounts:
                        raise CoreError(diagnostic('application.unknown.account'))
                    accounts = dict(store.accounts)
                    account = store.account
                    if action == "delete_account":
                        del accounts[key]
                        if account == key:
                            account = next(iter(accounts), "")
                    else:
                        account = key
                    store.persist(accounts=accounts, account=account)
                    store.publish()
            return None
        if action in ("setting", "theme", "locale", "detect_java"):
            java = self._app.get("java", JavaManager)
            if action == "detect_java":
                runtime = select_java_runtime(java.discover(), None if store.settings.get("javaVersion", "auto") == "auto" else int(store.settings["javaVersion"]))
                key, value = "javaPath", str(runtime.executable)
            elif action != "setting":
                key, value = action, key
            with store.lock:
                if key not in store.settings:
                    raise CoreError(diagnostic('application.unknown.setting'))
                if key.startswith('shortcut.'):
                    from Core.application.shortcuts import setting_valid
                    if not setting_valid(store.settings, key, value):
                        raise CoreError(diagnostic('application.shortcuts.invalid'))
                if isinstance(store.settings[key], bool) and value not in ("true", "false"):
                    raise CoreError(diagnostic('application.boolean.setting.must.be.true.or'))
                options = {"panelMode": ("hover", "button", "open", "closed", "both"), "panelLayout": ("overlay", "push"), "panelAlign": ("center", "top"), "buildView": ("cards", "list"), "coreView": ("cards", "list"), "javaVersion": ("auto", "8", "17", "21", "25"), "javaRestrictions": ("default", "none"), "closeAction": ("tray", "exit"), "launchAction": ("nothing", "minimize", "hide"), "finishAction": ("last", "each", "nothing"), "logMode": ("normal", "verbose"), "zipBatch": ("5", "10")}
                if key in options and value not in options[key]:
                    raise CoreError("Invalid setting value: " + key)
                if key in APPLICATION_SETTING_CHOICES and value not in APPLICATION_SETTING_CHOICES[key]:
                    raise CoreError("Invalid setting value: " + key)
                if key in APPLICATION_SETTING_RANGES:
                    minimum, maximum = APPLICATION_SETTING_RANGES[key]
                    if not value.isdigit() or not minimum <= int(value) <= maximum:
                        raise CoreError("Invalid setting value: " + key)
                if key in ("memoryMin", "memoryMax"):
                    if not value.isdigit():
                        raise CoreError(diagnostic('application.memory.must.be.a.number'))
                    settings = {**store.settings, key: value}
                    if not config.minimum_memory_mb <= int(settings["memoryMin"]) <= int(settings["memoryMax"]) <= store.memory_limit:
                        raise CoreError(diagnostic('application.memory.must.fit.the.physical.ram'))
                if key == "jvmArgs":
                    parse_jvm_arguments(value)
                if key == "javaPath" and value:
                    validated = java.validate_settings(JavaSettings(Path(value), int(store.settings["memoryMin"]), int(store.settings["memoryMax"])))
                    java.probe(validated.executable)
                    value = str(validated.executable)
                next_settings = {**store.settings, key: value == "true" if isinstance(store.settings[key], bool) else value}
                store.persist(settings=next_settings)
                store.publish()
                if key in ("logMode", "zipBatch"):
                    self._app.get("logs", LogManager).configure(str(store.settings.get("logMode", "normal")), int(store.settings.get("zipBatch", "5")))
            return None
        if action in ("decorate", "build_settings", "update_build"):
            self.guard(key)
            build = store.builds[key]
            if "minecraft" in fields or "loader" in fields or "loader_version" in fields:
                loader = fields.get("loader", build.loader)
                build = replace(build, minecraft=fields.get("minecraft", build.minecraft), loader=loader, loader_version="" if loader == "Vanilla" else fields.get("loader_version", build.loader_version))
                core_identifier(InstallRequest(build.minecraft, build.loader, build.loader_version))
            if action in ("decorate", "update_build"):
                build = replace(build, title=fields["title"], description=fields["description"], description_format=fields["description_format"], background=fields["background"], title_color=fields.get("title_color", build.title_color))
            if action in ("build_settings", "update_build"):
                minimum = int(fields["memory_min"]) if fields.get("memory_min") else None
                maximum = int(fields["memory_max"]) if fields.get("memory_max") else None
                effective_min = minimum if minimum is not None else int(store.settings["memoryMin"])
                effective_max = maximum if maximum is not None else int(store.settings["memoryMax"])
                if not config.minimum_memory_mb <= effective_min <= effective_max <= store.memory_limit:
                    raise CoreError(diagnostic('application.build.memory.limits.are.invalid'))
                path = fields.get("java_path", "")
                if path:
                    java = self._app.get("java", JavaManager)
                    validated = java.validate_settings(JavaSettings(Path(path), effective_min, effective_max))
                    java.probe(validated.executable)
                    path = str(validated.executable)
                parse_jvm_arguments(fields.get("jvm_args", ""))
                width = int(fields["width"]) if fields.get("width") else None
                height = int(fields["height"]) if fields.get("height") else None
                if (width is None) != (height is None) or width is not None and (width < MINIMUM_GAME_WINDOW_WIDTH or height < MINIMUM_GAME_WINDOW_HEIGHT):
                    raise CoreError(diagnostic('application.invalid.window.dimensions'))
                build = replace(build, java_path=path, memory_min=minimum, memory_max=maximum, jvm_args=fields.get("jvm_args", ""), width=width, height=height, fullscreen=fields.get("fullscreen") == "true")
            store.write_build(build)
            self.result("saved", key)
            return build
        if action == "delete":
            self.guard(key)
            safe_identifier(key)
            with store.lock:
                if key not in store.builds:
                    raise CoreError(diagnostic('application.unknown.build'))
                if value == "files":
                    files.remove_directory(f"{config.builds_directory}/{key}")
                else:
                    files.rename_file(f"{config.builds_directory}/{key}/{config.build_metadata_filename}", f"{config.builds_directory}/{key}/{config.build_metadata_filename}.removed")
                del store.builds[key]
                store.queue = [item for item in store.queue if item.owner_id != key]
                store.save()
                store.publish()
            return None
        if action == "install_build":
            build = store.builds[key]
            java_path = build.java_path or store.settings.get("javaPath", "")
            request = InstallRequest(build.minecraft, build.loader, build.loader_version, Path(java_path) if java_path else None)
            core_id = core_identifier(request)
            with store.lock:
                store.cores.setdefault(core_id, CoreChoice(core_id, build.minecraft, build.loader, build.loader_version))
                if self._app.get("installation", InstallationManager).ready(core_id):
                    store.scan_cores()
                    store.publish()
                    return None
                store.publish()
            task = self.install(request)
            self.result("task.core", core_id, task)
            return task
        if action == "download":
            core = store.cores.get(key) or self._app.get("catalogue", CatalogueManager).lookup(key)
            with store.lock:
                store.cores.setdefault(key, core)
                store.publish()
            request = InstallRequest(core.minecraft, core.loader, core.version, Path(store.settings["javaPath"]) if store.settings.get("javaPath") else None)
            task = self.install(request)
            self.result("task.core", key, task)
            return task
        if action in ("delete_core", "download"):
            core = store.cores[key]
            if any(task.title == "Install " + key and task.state in ("queued", "running", "retrying", "paused", "cancelling") for task in self._app.get("tasks", TaskManager).snapshots()):
                raise CoreError(diagnostic('application.core.installation.is.still.active'))
            if core.loader == "Vanilla":
                active = {task.task_id for task in self._app.get("tasks", TaskManager).snapshots() if task.state in ("queued", "running", "retrying", "paused", "cancelling")}
                if any(item.minecraft_version == core.minecraft and item.loader != "Vanilla" and item.task_id in active for item in self._app.get("installation", InstallationManager).tasks()):
                    raise CoreError(diagnostic('application.core.is.required.by.an.active'))
            for build in store.builds.values():
                if (build.minecraft, build.loader, build.loader_version) == (core.minecraft, core.loader, core.version) or core.loader == "Vanilla" and build.minecraft == core.minecraft:
                    self.guard(build.id)
            files.remove_directory(f"{config.cores_directory}/{key}")
            with store.lock:
                store.scan_cores()
                store.publish()
            return None
        if action == "refresh_installed":
            with store.lock:
                store.scan_cores()
                store.publish()
            return None
        if action in ("open_core_folder", "open_build_folder"):
            base = config.cores_directory if action == "open_core_folder" else config.builds_directory
            safe_identifier(key)
            directory = self._app.get("editor_files", EditorFilesManager).path(key, value) if action == "open_build_folder" and value else f"{base}/{key}"
            self.result("open_path", path=str(files.ensure_directory(directory)))
            return None
        if action == "play":
            build = store.builds[key]
            account = store.accounts.get(value or store.account)
            if account is None:
                raise CoreError(diagnostic('application.select.an.offline.account.before.launching'))
            launch = self._app.get("launch", LaunchManager)
            if any(client.build_id == key and client.state in ("starting", "running", "closing") for client in launch.snapshots()):
                raise CoreError(diagnostic('application.build.is.already.running'))
            core_id = core_identifier(InstallRequest(build.minecraft, build.loader, build.loader_version))
            if not self._app.get("installation", InstallationManager).ready(core_id):
                raise CoreError(diagnostic('application.minecraft.installation.is.incomplete.finish.downloading'))
            receipt = self._app.get("installation", InstallationManager).receipt(core_id)
            profile = self._app.get("metadata", MetadataManager).load_profile(receipt.profile_path)
            java = self._app.get("java", JavaManager)
            path = build.java_path or store.settings["javaPath"]
            executable = Path(path) if path else select_java_runtime(java.discover(), profile.java_major).executable
            settings = JavaSettings(executable, int(store.settings["memoryMin"]), int(store.settings["memoryMax"]), parse_jvm_arguments(store.settings["jvmArgs"]))
            overrides = JavaOverrides(Path(build.java_path) if build.java_path else None, build.memory_min, build.memory_max, parse_jvm_arguments(build.jvm_args) if build.jvm_args else None)
            request = LaunchRequest(key, core_id, AccountSession(account.name, account.uuid, "0"), settings, overrides, build.width, build.height, build.fullscreen, self._command.launch_origin)
            cancellation.check()
            return launch.submit(request)
        if action in ("close_client", "kill_client"):
            launch = self._app.get("launch", LaunchManager)
            return launch.request_close(key) if action == "close_client" else launch.kill(key, confirmed=True)
        if action == "editor_scan":
            return self._app.get("editor_files", EditorFilesManager).scan(key, cancellation)
        if action in ("read_file", "save_file"):
            editor = self._app.get("editor_files", EditorFilesManager)
            path = editor.writable_path(key, fields["path"]) if action == "save_file" else editor.path(key, fields["path"])
            if action == "save_file":
                if not editor.is_config(fields["path"]):
                    self.guard(key)
                files.write_bytes(path, value.encode("utf-8"), cancellation)
                self.result("file_saved", key, value, fields["path"])
            else:
                text = files.read(path).decode("utf-8-sig")
                self.result("file_read", key, text, fields["path"])
            return None
        if action == "mod_search":
            request = ModSearchRequest(key, fields.get("request_id", ""), value, int(fields.get("offset", "0")), int(fields.get("limit", MOD_CATALOGUE_PAGE_SIZE)), fields.get("category", ""), fields.get("sort", ""), fields.get('minecraft', ''), fields.get('loader', ''), fields.get('content_kind', 'mod'))
            return self._app.get("modrinth", ModrinthManager).search(store.builds[key], value, cancellation, request)
        if action == "mod_project":
            return self._app.get('modrinth', ModrinthManager).project(store.builds[key], value, fields.get('request_id', ''), cancellation, fields.get('content_kind', 'mod'))
        if action == "mod_icons":
            return self._app.get('modrinth', ModrinthManager).icons(json.loads(value), cancellation)
        if action == "mod_filters":
            return self._app.get('modrinth', ModrinthManager).filters(key, cancellation, fields.get('content_kind', 'mod'))
        if action in ("add_mod", "remove_queued_mod"):
            version_id = fields.get('version_id', '')
            if action == 'add_mod':
                content_kind = fields.get('content_kind', 'mod')
                project = fields.get('id', modrinth_project(value, content_kind))
                return self._app.get('mod_queue', ModQueueManager).add(store.builds[key], project, version_id, fields.get('title') or project, cancellation, fields.get('window_key', ''), content_kind)
            with store.lock:
                queue = [item for item in store.queue if not (item.owner_id == key and (item.queue_id or item.id) == value and item.state == "queued")]
                store.persist(queue=queue)
                store.publish()
            return None
        if action == 'resolve_mod_queue':
            local = self._app.get('mod_imports', ModImportManager).handles(value)
            if local and fields['choice'] != 'cancel':
                try:
                    self.guard(key)
                except BaseException:
                    self._app.get('mod_imports', ModImportManager).answer(key, value, 'cancel', cancellation)
                    raise
            result = self._app.get('mod_queue', ModQueueManager).answer(key, value, fields['choice'], cancellation)
            if local:
                self._app.get('editor_files', EditorFilesManager).scan(key, cancellation)
            return result
        if action == "sync_and_play":
            if store.accounts.get(value or store.account) is None:
                raise CoreError(diagnostic('application.select.an.offline.account.before.launching'))
            ApplicationOperation(self._app, ApplicationCommand("sync_mods", key)).run_command(task_id, cancellation)
            cancellation.check()
            return ApplicationOperation(self._app, ApplicationCommand("play", key, value, launch_origin=self._command.launch_origin)).run(task_id, cancellation)
        if action == "sync_mods":
            queue_manager = self._app.get('mod_queue', ModQueueManager)
            selected_kind = fields.get('content_kind', '')
            queue = queue_manager.synchronization_queue(key, selected_kind)
            self.guard_content_queue(key, queue)
            tasks = self._app.get("tasks", TaskManager)
            tasks.start_stage(task_id, "metadata")
            self.result("task.mod", key, task_id)
            try:
                with store.lock:
                    store.queue = [replace(item, state="downloading") if item in queue else item for item in store.queue]
                    store.publish()
                artifacts = {}
                queue_manager.validate_replacements(queue, cancellation)
                legacy = tuple(item for item in queue if item.artifact is None)
                resolved = tuple(queue_manager.staged_artifact(item) for item in queue if item.artifact is not None)
                if legacy:
                    resolved += self._app.get("modrinth", ModrinthManager).resolve_sources(store.builds[key], tuple(item.source for item in legacy), cancellation, tuple(item.id for item in queue), tuple((modrinth_project(item.source), item.version_id) for item in queue if item.version_id))
                for artifact in resolved:
                    previous = artifacts.get(artifact.relative_path.casefold())
                    if previous is not None and previous != artifact:
                        raise CoreError(diagnostic('application.selected.mods.have.conflicting.dependency.files'))
                    artifacts[artifact.relative_path.casefold()] = artifact
                self.guard_content_queue(key, queue)
                tasks.start_stage(task_id, "download")
                item_keys = tuple((queue_manager.staged_artifact(item).relative_path, item.queue_id or item.id) for item in queue if item.artifact is not None)
                self._app.get("downloads", DownloadManager).execute(DownloadBatch(tuple(artifacts.values()), "Mods", item_keys), task_id, cancellation)
                tasks.start_stage(task_id, "finalize")
                if queue:
                    self.guard_content_queue(key, queue)
                    queue_manager.finalize(queue, cancellation)
                with store.lock:
                    remaining = [item for item in store.queue if item not in tuple(replace(old, state="downloading") for old in queue)]
                    store.persist(queue=remaining)
            finally:
                with store.lock:
                    store.queue = [replace(item, state="queued") if item.owner_id == key else item for item in store.queue]
                    store.publish()
            return self._app.get("editor_files", EditorFilesManager).scan(key, cancellation)
        if action in ("drop_mod", "import_files", "toggle_mod", "delete_file"):
            editor = self._app.get("editor_files", EditorFilesManager)
            if action in ("drop_mod", "toggle_mod"):
                self.guard(key)
            elif action == "delete_file":
                self.guard(key, (value,))
            if action in ("drop_mod", "import_files"):
                sources = json.loads(value)
                if not isinstance(sources, list) or any(not isinstance(source, str) for source in sources):
                    raise CoreError(diagnostic('application.imported.files.must.be.a.json'))
                if action == "drop_mod" and store.builds[key].loader == "Vanilla":
                    raise CoreError(diagnostic('application.vanilla.builds.do.not.support.mods'))
                directory = "mods" if action == "drop_mod" else fields.get("directory", "")
                if directory:
                    checked_relative(directory)
                imports = []
                for source in sources:
                    parsed = urlsplit(source)
                    if parsed.scheme and parsed.scheme != "file" and not re.match(r"^[A-Za-z]:", source) or parsed.scheme == "file" and parsed.netloc not in ("", "localhost"):
                        raise CoreError(diagnostic('application.only.local.files.can.be.imported'))
                    path = Path(unquote(parsed.path).removeprefix("/") if parsed.scheme == "file" and re.match(r"/[A-Za-z]:", parsed.path) else unquote(parsed.path) if parsed.scheme == "file" else source)
                    if path.suffix.lower() == '.ugtheme':
                        raise CoreError(diagnostic('editor.theme.files.rejected'))
                    if action == "drop_mod" and not path.name.lower().endswith(".jar"):
                        raise CoreError(diagnostic('application.only.jar.mods.can.be.dropped'))
                    destination = editor.writable_path(key, (directory + "/" if directory else "") + path.name)
                    if action == "import_files" and files.external_directory(path):
                        parent = f"{config.builds_directory}/{key}" + ("/" + directory if directory else "")
                        for source, target, folder in files.import_plan(path, parent, cancellation):
                            if not folder and source.suffix.lower() == '.ugtheme':
                                raise CoreError(diagnostic('editor.theme.files.rejected'))
                            relative = target.removeprefix(f"{config.builds_directory}/{key}/")
                            editor.writable_path(key, relative)
                            imports.append((source, target, folder))
                    else:
                        files.validate_import_file(path, config.mod_jar_bytes if action == "drop_mod" else config.import_file_bytes)
                        imports.append((path, destination, False))
                self.guard(key, tuple(destination.removeprefix(f"{config.builds_directory}/{key}/") for _, destination, _ in imports))
                prefix = f'{config.builds_directory}/{key}/mods/'
                if any(destination.casefold().startswith(prefix.casefold()) and destination.lower().endswith(('.jar', '.jar.disabled')) for path, destination, folder in imports if not folder):
                    self._app.get('mod_imports', ModImportManager).add(store.builds[key], tuple(imports), cancellation, fields.get('window_key', ''))
                    return editor.scan(key, cancellation)
                for path, destination, folder in imports:
                    if folder:
                        files.ensure_directory(destination)
                    else:
                        files.import_file(path, Artifact("", destination), cancellation, config.mod_jar_bytes if action == "drop_mod" else config.import_file_bytes)
            elif action == "toggle_mod":
                if not value.startswith("mods/") or not value.endswith((".jar", ".jar.disabled")):
                    raise CoreError(diagnostic('application.only.mod.jar.files.can.be'))
                source = editor.writable_path(key, value)
                destination = source.removesuffix(".disabled") if source.endswith(".disabled") else source + ".disabled"
                files.rename_file(source, destination)
            else:
                source = editor.writable_path(key, value)
                if files.is_directory(source):
                    files.remove_directory(source)
                else:
                    files.remove_file(source)
            return editor.scan(key, cancellation)
        raise CoreError(diagnostic('application.unknown.application.command', action))

    def install(self, request: InstallRequest) -> str:
        return self._app.get("installation", InstallationManager).submit(request)

    def prepare_resources(self) -> None:
        if dict(self._command.fields).get("prepare_resources", "false") != "true":
            return
        task = self._app.get("installation", InstallationManager).prepare_resources()
        if task:
            self.result("task.resources", text=task)
