from Core.application.diagnostics import diagnostic
import re

from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from threading import RLock, Thread, current_thread
from uuid import uuid4

from Core.application.contracts import Argument, Cancelled, ClientSnapshot, CoreError, CoreEvent, JavaSettings, LaunchPlan, LaunchRequest, PlatformSpec, VersionProfile
from Core.installation.installation import InstallationManager, MetadataManager
from Core.game.java import JavaManager, merge_java
from Core.game.metadata import allowed, host_platform, native_artifact, object_value, profile_artifacts
from Core.game.processes import ManagedProcess, ProcessSpec
from Core.game.process_manager import ProcessDriver
from Core.application.router import AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager, NativeArchive, safe_identifier
from Core.application.tasks import Cancellation, TaskManager


def substitute(value: str, variables: tuple[tuple[str, str], ...]) -> str:
    mapping = dict(variables)
    names = re.findall(r"\$\{([^}]+)\}", value)
    for name in names:
        if name not in mapping:
            raise CoreError(diagnostic('launch.unsupported.launcher.argument.placeholder', name))
    for name in names:
        value = value.replace("${" + name + "}", mapping[name])
    return value


def expand_arguments(profile_arguments: tuple[Argument, ...], target: PlatformSpec, variables: tuple[tuple[str, str], ...]) -> tuple[str, ...]:
    return tuple(substitute(value, variables) for argument in profile_arguments if allowed(argument.rules, target) for value in argument.values)


def build_launch_plan(request: LaunchRequest, settings: JavaSettings, profile: VersionProfile, config: CoreConfig, target: PlatformSpec, native_directory: Path, log_path: Path) -> LaunchPlan:
    if not profile.main_class or not re.fullmatch(r"[A-Za-z_$][\w.$]*", profile.main_class):
        raise CoreError(diagnostic('launch.profile.does.not.declare.a.valid'))
    if profile.client is None:
        raise CoreError(diagnostic('launch.profile.has.no.client.artifact'))
    if not request.account.username or not request.account.uuid:
        raise CoreError(diagnostic('launch.an.account.session.must.be.supplied'))
    has_resolution = request.width is not None and request.height is not None
    if (request.width is None) != (request.height is None) or (has_resolution and (request.width < 1 or request.height < 1)):
        raise CoreError(diagnostic('launch.window.width.and.height.must.both'))
    target = replace(target, features=(*target.features, ("has_custom_resolution", has_resolution)))
    root = config.root.resolve()
    game_directory = root / config.builds_directory / request.build_id
    classpath_entries = [root / library.artifact.relative_path for library in profile.libraries if library.artifact and allowed(library.rules, target)]
    classpath_entries.append(root / profile.client.relative_path)
    separator = ";" if target.os_name == "windows" else ":"
    classpath = separator.join(str(path) for path in classpath_entries)
    cache_root = root / config.libs_directory
    library_root = root / config.cores_directory / config.cache_directory if profile.parent_id else cache_root
    variables = (("auth_player_name", request.account.username), ("auth_uuid", request.account.uuid), ("auth_access_token", request.account.access_token), ("auth_session", f"token:{request.account.access_token}:{request.account.uuid}"), ("user_type", request.account.user_type), ("user_properties", "{}"), ("auth_xuid", request.account.xuid), ("clientid", request.account.client_id), ("version_name", profile.version_id), ("version_type", profile.version_type or "release"), ("game_directory", str(game_directory)), ("assets_root", str(cache_root / "assets")), ("assets_index_name", profile.asset_index.index_id if profile.asset_index else ""), ("natives_directory", str(native_directory)), ("library_directory", str(library_root / "libraries")), ("classpath", classpath), ("classpath_separator", separator), ("launcher_name", config.launcher_name), ("launcher_version", config.launcher_version), ("resolution_width", str(request.width or 0)), ("resolution_height", str(request.height or 0)))
    jvm = expand_arguments(profile.jvm_arguments, target, variables)
    if not profile.jvm_arguments:
        jvm = (f"-Djava.library.path={native_directory}", "-cp", classpath)
    logging_arguments = ()
    if profile.logging:
        logging_arguments = (substitute(profile.logging.argument, (("path", str(root / profile.logging.artifact.relative_path)),)),)
    game = expand_arguments(profile.game_arguments, target, variables)
    if request.fullscreen:
        game += ("--fullscreen",)
    if not game:
        raise CoreError(diagnostic('launch.profile.does.not.declare.game.arguments'))
    argv = (str(settings.executable), *settings.extra_arguments, f"-Xms{settings.minimum_memory_mb}M", f"-Xmx{settings.maximum_memory_mb}M", *jvm, *logging_arguments, profile.main_class, *game)
    if any("\x00" in argument for argument in argv):
        raise CoreError(diagnostic('launch.process.arguments.contain.nul.characters'))
    return LaunchPlan(argv, request.build_id, game_directory, log_path)


class LaunchManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config
        self._lock = RLock()
        self._clients: dict[str, ClientSnapshot] = {}
        self._processes: dict[str, ManagedProcess] = {}
        self._monitors: dict[str, Thread] = {}
        self._native_paths = {}
        self._closed = False

    def submit(self, request: LaunchRequest) -> str:
        if request.launch_origin not in ("launcher", "editor", "cli"):
            raise CoreError(diagnostic('launch.unknown.launch.origin'))
        safe_identifier(request.build_id)
        safe_identifier(request.core_id)
        key = request.build_id.casefold()
        with self._lock:
            if self._closed:
                raise CoreError(diagnostic('launch.launch.manager.is.closed'))
            current = self._clients.get(key)
            if current and current.state in ("starting", "running", "closing"):
                raise CoreError(diagnostic('launch.this.build.is.already.running'))
            self._set(ClientSnapshot(request.build_id, "starting", launch_origin=request.launch_origin))
        try:
            return self._app.get("tasks", TaskManager).submit(f"Launch {request.build_id}", LaunchOperation(self._app, request).run)
        except Exception as error:
            self.failed(request.build_id, str(error))
            raise

    def started(self, build_id: str, process: ManagedProcess, native_relative_path: str) -> None:
        key = build_id.casefold()
        monitor = Thread(target=self._monitor, args=(build_id, process, native_relative_path), name=f"minecraft-{build_id}", daemon=True)
        with self._lock:
            if self._closed:
                raise CoreError(diagnostic('launch.launch.manager.closed.before.process.ownership'))
            self._processes[key] = process
            self._monitors[key] = monitor
            self._native_paths[key] = native_relative_path
            current = self._clients.get(key, ClientSnapshot(build_id, "starting"))
            self._set(replace(current, state="running", pid=process.pid, exit_code=None, error=""))
        monitor.start()

    def _monitor(self, build_id: str, process: ManagedProcess, native_relative_path: str) -> None:
        error = ""
        exit_code = None
        try:
            exit_code = process.wait()
        except Exception as failure:
            error = str(failure)
        finally:
            if getattr(process, 'detached', False):
                process.dispose()
                return
            try:
                process.dispose()
                self._app.get("files", FileManager).remove_directory(native_relative_path)
            except Exception as failure:
                error = error or str(failure)
            with self._lock:
                self._processes.pop(build_id.casefold(), None)
                self._monitors.pop(build_id.casefold(), None)
                self._native_paths.pop(build_id.casefold(), None)
                current = self._clients[build_id.casefold()]
                self._set(replace(current, state="failed" if error else "exited", pid=process.pid, exit_code=exit_code, error=error))

    def failed(self, build_id: str, error: str) -> None:
        with self._lock:
            current = self._clients.get(build_id.casefold(), ClientSnapshot(build_id, "starting"))
            self._set(replace(current, state="failed", error=error))

    def _set(self, snapshot: ClientSnapshot) -> None:
        self._clients[snapshot.build_id.casefold()] = snapshot
        self._app.get("events", EventManager).publish(CoreEvent("client", snapshot))

    def request_close(self, build_id: str) -> str:
        return self._app.get("tasks", TaskManager).submit(f"Close {build_id}", ClientControlOperation(self._app, build_id, False).run)

    def kill(self, build_id: str, confirmed: bool) -> str:
        if confirmed is not True:
            raise CoreError(diagnostic('launch.force.stop.requires.an.explicit.confirmed'))
        return self._app.get("tasks", TaskManager).submit(f"Kill {build_id}", ClientControlOperation(self._app, build_id, True).run)

    def control(self, build_id: str, force: bool) -> bool:
        key = build_id.casefold()
        with self._lock:
            process = self._processes.get(key)
            if process is None:
                raise CoreError(diagnostic('launch.build.has.no.running.client'))
            if force:
                process.kill()
                success = True
            else:
                success = process.request_close()
            old = self._clients[key]
            if success:
                self._set(replace(old, state="closing"))
            return success

    def snapshots(self) -> tuple[ClientSnapshot, ...]:
        with self._lock:
            return tuple(self._clients.values())

    def has_active_clients(self) -> bool:
        with self._lock:
            return any(client.state in ("starting", "running", "closing") for client in self._clients.values())

    def export_clients(self, target_pid):
        with self._lock:
            if any(item.state != 'running' for item in self._clients.values() if item.state in ('starting', 'running', 'closing')):
                raise CoreError(diagnostic('updates.client_transfer'))
            result = []
            for key, process in self._processes.items():
                values = process.duplicate(target_pid)
                result.append(dict(snapshot=asdict(self._clients[key]), handles=values, natives=self._native_paths[key]))
            return result

    def detach_clients(self):
        with self._lock:
            self._closed = True
            for process in self._processes.values():
                process.detached = True
            self._processes.clear()
            self._clients.clear()
            self._native_paths.clear()

    def adopt_clients(self, source_pid, clients):
        from Core.game.processes import WindowsApi, WindowsManagedProcess
        api = WindowsApi()
        adopted = []
        try:
            for item in clients:
                snapshot = ClientSnapshot(**item['snapshot'])
                safe_identifier(snapshot.build_id)
                expected = f'{self._config.builds_directory}/{snapshot.build_id}/{self._config.build_runtime_directory}/{self._config.natives_directory}/'
                if not item['natives'].startswith(expected) or '..' in item['natives'].split('/'):
                    raise CoreError(diagnostic('updates.client_transfer'))
                process = WindowsManagedProcess.adopt(api, source_pid, item['handles'])
                adopted.append(process)
                self._clients[snapshot.build_id.casefold()] = snapshot
                self.started(snapshot.build_id, process, item['natives'])
        except BaseException:
            for process in adopted:
                process.detached = True
                process.dispose()
            raise

    def close(self, force: bool = False) -> None:
        with self._lock:
            if self.has_active_clients() and not force:
                raise CoreError(diagnostic('launch.launcher.cannot.shut.down.while.clients'))
            self._closed = True
            processes = tuple(self._processes.values())
            monitors = tuple(self._monitors.values())
        for process in processes:
            process.kill()
        for monitor in monitors:
            if monitor is not current_thread():
                monitor.join(self._config.client_shutdown_timeout)
                if monitor.is_alive():
                    raise CoreError(diagnostic('launch.client.monitor.did.not.stop'))


class LaunchOperation:
    def __init__(self, app: AppManager, request: LaunchRequest) -> None:
        self._app = app
        self._request = request

    def run(self, task_id: str, cancellation: Cancellation) -> ClientSnapshot:
        manager = self._app.get("launch", LaunchManager)
        native_relative = ""
        process = None
        try:
            cancellation.check()
            config = self._app.get("config", CoreConfig)
            files = self._app.get("files", FileManager)
            receipt = self._app.get("installation", InstallationManager).receipt(self._request.core_id)
            profile = self._app.get("metadata", MetadataManager).load_profile(receipt.profile_path)
            build_meta = object_value(files.json(f"{config.builds_directory}/{self._request.build_id}/{config.build_metadata_filename}"), "build")
            if build_meta.get("id") != self._request.build_id:
                raise CoreError(diagnostic('launch.build.metadata.id.does.not.match'))
            java = self._app.get("java", JavaManager)
            settings = java.validate_settings(merge_java(self._request.java, self._request.overrides))
            runtime = java.probe(settings.executable)
            if profile.java_major and runtime.major_version < profile.java_major:
                raise CoreError(diagnostic('launch.minecraft.requires.java.or.newer', profile.java_major))
            target = host_platform()
            if runtime.bits != int(target.bits):
                raise CoreError(diagnostic('launch.java.architecture.must.match.the.selected'))
            if not self._app.get("installation", InstallationManager).ready(self._request.core_id):
                raise CoreError(diagnostic('launch.minecraft.installation.is.incomplete.finish.downloading'))
            native_relative = f"{config.builds_directory}/{self._request.build_id}/{config.build_runtime_directory}/{config.natives_directory}/{uuid4().hex}"
            archives = tuple(NativeArchive(native.relative_path, library.excludes) for library in profile.libraries if allowed(library.rules, target) and (native := native_artifact(library, target)))
            native_path = files.extract_natives(archives, native_relative, cancellation)
            log_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_path = files.path(f"{config.builds_directory}/{self._request.build_id}/{config.build_logs_directory}/{log_stamp}-{uuid4().hex[:8]}.log")
            plan = build_launch_plan(self._request, settings, profile, config, target, native_path, log_path)
            cancellation.check()
            process = self._app.get("processes", ProcessDriver).spawn(ProcessSpec(plan.argv, plan.working_directory, plan.log_path))
            cancellation.check()
            manager.started(self._request.build_id, process, native_relative)
            return ClientSnapshot(self._request.build_id, "running", process.pid, launch_origin=self._request.launch_origin)
        except Exception as error:
            if process:
                process.dispose()
            if native_relative:
                self._app.get("files", FileManager).remove_directory(native_relative)
            manager.failed(self._request.build_id, "Launch cancelled" if isinstance(error, Cancelled) else str(error))
            raise


class ClientControlOperation:
    def __init__(self, app: AppManager, build_id: str, force: bool) -> None:
        self._app = app
        self._build_id = build_id
        self._force = force

    def run(self, task_id: str, cancellation: Cancellation) -> bool:
        cancellation.check()
        return self._app.get("launch", LaunchManager).control(self._build_id, self._force)
