from Core.application.diagnostics import diagnostic
import json
import os
import re

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from Core.application.contracts import Artifact, CoreError, Digest, DownloadBatch, HttpRequest, InstallRequest, JavaSettings, TaskStage, VersionProfile
from Core.network.downloads import DownloadManager
from Core.installation.installer_contracts import InstallerPlan, InstallerResult
from Core.installation.installer_metadata import checked_installer_url, installer_url, manifest_main_class, parse_installer, resolve_installer_value
from Core.game.java import JavaManager, select_java_runtime
from Core.game.metadata import maven_path, object_value, parse_artifact, parse_json, parse_profile, string_value
from Core.network.network import NetworkManager
from Core.game.process_manager import ProcessDriver
from Core.game.processes import ProcessSpec
from Core.application.router import AppManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager, checked_relative
from Core.application.tasks import Cancellation, TaskManager


class ForgeInstallerManager:
    def __init__(self, app: AppManager, config: CoreConfig) -> None:
        self._app = app
        self._config = config

    def install(self, request: InstallRequest, parent: VersionProfile, parent_data: bytes, task_id: str, cancellation: Cancellation) -> InstallerResult:
        url = installer_url(request, self._config)
        network = self._app.get("network", NetworkManager)
        checksum = network.read(HttpRequest(url + ".sha1"), cancellation, 4096).decode("ascii").strip().split()[0]
        archive = Artifact(url, f"{self._config.cores_directory}/{self._config.cache_directory}/{self._config.installer_directory}/{url.rsplit('/', 1)[1]}", digests=(Digest("sha1", checksum),))
        downloads = self._app.get("downloads", DownloadManager)
        downloads.fetch(archive, cancellation)
        files = self._app.get("files", FileManager)
        install_data = files.archive_member(archive.relative_path, "install_profile.json", self._config.maximum_metadata_bytes)
        install = parse_json(install_data)
        member = string_value(install.get("json"), "installer.json").removeprefix("/")
        checked_relative(member)
        plan = parse_installer(install_data, files.archive_member(archive.relative_path, member, self._config.maximum_metadata_bytes), request, self._config)
        java = self._app.get("java", JavaManager)
        if request.java_executable is None:
            runtime = select_java_runtime(java.discover(), parent.java_major)
        else:
            executable = java.validate_settings(JavaSettings(request.java_executable)).executable
            runtime = java.probe(executable)
        if parent.java_major is not None and runtime.major_version < parent.java_major:
            raise CoreError(diagnostic('forge_installation.installer.java.is.older.than.the'))
        work = f"{self._config.cores_directory}/{self._config.cache_directory}/{self._config.installer_work_directory}/{uuid4().hex}"
        files.ensure_directory(work)
        try:
            return ForgeInstallOperation(self._app, plan, archive, work, runtime.executable, parent, parent_data).run(task_id, cancellation)
        finally:
            files.remove_directory(work)

    def close(self) -> None:
        pass


class ForgeInstallOperation:
    def __init__(self, app: AppManager, plan: InstallerPlan, archive: Artifact, work: str, java: Path, parent: VersionProfile, parent_data: bytes) -> None:
        self._app = app
        self._plan = plan
        self._archive = archive
        self._work = work
        self._java = java
        self._parent = parent
        self._parent_data = parent_data

    def run(self, task_id: str, cancellation: Cancellation) -> InstallerResult:
        config = self._app.get("config", CoreConfig)
        files = self._app.get("files", FileManager)
        downloads = self._app.get("downloads", DownloadManager)
        library_root = files.ensure_directory(self._work + "/libraries").as_posix()
        tasks = self._app.get("tasks", TaskManager)
        stages = (TaskStage("installer.dependencies"),) + tuple(TaskStage("installer.processor." + str(index)) for index in range(len(self._plan.processors))) + (TaskStage("installer.finalize"),)
        tasks.expand_stage(task_id, "installer", stages)
        tasks.start_stage(task_id, "installer.dependencies")
        variables = self._variables(library_root, cancellation)
        outputs = tuple(tuple(self._output(path, digest, variables, library_root) for path, digest in processor.outputs) for processor in self._plan.processors)
        generated = {artifact.relative_path for group in outputs for artifact in group}
        child = parse_profile(parse_json(self._plan.profile), config)
        client_libraries = tuple(library.artifact for library in child.libraries if library.artifact)
        dependencies = {}
        for artifact in (*self._plan.libraries, *client_libraries):
            suffix = artifact.relative_path.split("/libraries/", 1)[1]
            stage = replace(artifact, relative_path=self._work + "/libraries/" + suffix)
            if stage.relative_path in generated or not artifact.url:
                continue
            checked_installer_url(artifact.url, config)
            if not artifact.digests:
                checksum = self._app.get("network", NetworkManager).read(HttpRequest(artifact.url + ".sha1"), cancellation, 4096).decode("ascii").strip().split()[0]
                artifact = replace(artifact, digests=(Digest("sha1", checksum),))
            previous = dependencies.get(artifact.relative_path)
            if previous is not None:
                hashes = {digest.algorithm: digest.value.lower() for digest in previous.digests}
                if any(digest.algorithm in hashes and hashes[digest.algorithm] != digest.value.lower() for digest in artifact.digests) or (previous.size is not None and artifact.size is not None and previous.size != artifact.size):
                    raise CoreError(diagnostic('forge_installation.installer.declares.conflicting.library.artifacts'))
            else:
                dependencies[artifact.relative_path] = artifact
        if self._parent.client is None:
            raise CoreError(diagnostic('forge_installation.installer.requires.a.minecraft.client.artifact'))
        downloads.execute(DownloadBatch((self._parent.client, *dependencies.values()), "Installer dependencies"), task_id, cancellation)
        for artifact in dependencies.values():
            suffix = artifact.relative_path.split("/libraries/", 1)[1]
            files.copy_file(artifact.relative_path, replace(artifact, relative_path=self._work + "/libraries/" + suffix), cancellation)
        self._extract_embedded(tuple((*self._plan.libraries, *client_libraries)), generated, cancellation)
        dated = datetime.now().strftime("%Y-%m-%d")
        for index, processor in enumerate(self._plan.processors):
            cancellation.check()
            tasks.start_stage(task_id, "installer.processor." + str(index))
            expected = outputs[index]
            if expected and all(files.verify(artifact, cancellation) for artifact in expected):
                continue
            arguments = tuple(resolve_installer_value(value, variables, library_root) for value in processor.arguments)
            if self._download_mappings(arguments, task_id, cancellation):
                pass
            else:
                jar = self._work + "/libraries/" + processor.jar
                main = manifest_main_class(files.archive_member(jar, "META-INF/MANIFEST.MF", config.maximum_metadata_bytes))
                classpath_paths = tuple(files.path(self._work + "/libraries/" + path) for path in (processor.jar, *processor.classpath))
                if any(not path.is_file() for path in classpath_paths):
                    raise CoreError(diagnostic('forge_installation.installer.processor.dependency.is.missing'))
                separator = ";" if os.name == "nt" else ":"
                log = files.path(f"{config.logs_directory}/{config.installer_logs_directory}/{dated}/{task_id}-{index + 1}.log")
                spec = ProcessSpec((str(self._java), "-cp", separator.join(str(path) for path in classpath_paths), main, *arguments), files.path(self._work), log)
                self._app.get("processes", ProcessDriver).execute(spec, cancellation, config.installer_process_timeout, config.control_wait_interval)
            for artifact in expected:
                if not files.verify(artifact, cancellation):
                    raise CoreError(diagnostic('forge_installation.installer.processor.output.failed.verification', artifact.relative_path))
            tasks.progress(task_id, 0, None, 1.0)
        tasks.start_stage(task_id, "installer.finalize")
        inventory = dict(dependencies)
        declared_data = dict(self._plan.data)
        data_outputs = []
        for name, value in self._plan.data:
            if value.startswith("[") and value.endswith("]"):
                relative = self._work + "/libraries/" + maven_path(value[1:-1])
                if not files.exists(relative):
                    referenced = any("{" + name + "}" in argument for processor in self._plan.processors for argument in processor.arguments)
                    if referenced:
                        raise CoreError(diagnostic('forge_installation.installer.did.not.generate.its.declared', name))
                    continue
                expected = declared_data.get(name + "_SHA")
                if expected is not None:
                    artifact = self._output(value, resolve_installer_value("{" + name + "_SHA}", variables, library_root), variables, library_root)
                    if not files.verify(artifact, cancellation):
                        raise CoreError(diagnostic('forge_installation.installer.client.data.failed.verification', name))
                else:
                    artifact = files.fingerprint(relative, cancellation)
                data_outputs.append(artifact)
        for group in (*outputs, tuple(data_outputs)):
            for artifact in group:
                if "/libraries/" in artifact.relative_path:
                    suffix = artifact.relative_path.split("/libraries/", 1)[1]
                    destination = replace(artifact, relative_path=f"{config.cores_directory}/{config.cache_directory}/libraries/{suffix}")
                    files.copy_file(artifact.relative_path, destination, cancellation)
                    inventory[destination.relative_path] = destination
        normalized = parse_json(self._plan.profile)
        for raw in normalized.get("libraries", []):
            entry = object_value(raw, "library")
            library = parse_profile({"id": self._plan.version_id, "inheritsFrom": self._plan.minecraft_version, "libraries": [entry]}, config).libraries[0]
            if library.artifact is None:
                continue
            artifact = library.artifact
            suffix = artifact.relative_path.split("/libraries/", 1)[1]
            stage = self._work + "/libraries/" + suffix
            if artifact.relative_path not in inventory:
                local = replace(files.fingerprint(stage, cancellation), relative_path=artifact.relative_path)
                files.copy_file(stage, local, cancellation)
                inventory[local.relative_path] = local
            actual = inventory[artifact.relative_path]
            hashes = {digest.algorithm: digest.value for digest in actual.digests}
            entry["downloads"] = {**object_value(entry.get("downloads", {}), "downloads"), "artifact": {"url": actual.url, "path": suffix, "size": files.size(actual.relative_path), **hashes}}
        return InstallerResult(json.dumps(normalized).encode("utf-8"), (self._archive, *inventory.values()))

    def _variables(self, library_root: str, cancellation: Cancellation) -> tuple[tuple[str, str], ...]:
        files = self._app.get("files", FileManager)
        variables = []
        for name, value in self._plan.data:
            if value.startswith("[") and value.endswith("]"):
                resolved = library_root + "/" + maven_path(value[1:-1])
            elif value.startswith("'") and value.endswith("'"):
                resolved = value[1:-1]
            else:
                member = value.removeprefix("/")
                checked_relative(member)
                destination = self._work + "/data/" + member
                config = self._app.get("config", CoreConfig)
                files.write_bytes(destination, files.archive_member(self._archive.relative_path, member, config.installer_archive_bytes), cancellation)
                resolved = files.path(destination).as_posix()
            variables.append((name, resolved))
        if self._parent.client is None:
            raise CoreError(diagnostic('forge_installation.missing.minecraft.client'))
        return (*variables, ("SIDE", "client"), ("MINECRAFT_JAR", files.path(self._parent.client.relative_path).as_posix()), ("MINECRAFT_VERSION", self._plan.minecraft_version), ("ROOT", files.path(self._work).as_posix()), ("INSTALLER", files.path(self._archive.relative_path).as_posix()), ("LIBRARY_DIR", library_root))

    def _output(self, path: str, digest: str, variables: tuple[tuple[str, str], ...], library_root: str) -> Artifact:
        files = self._app.get("files", FileManager)
        resolved = Path(resolve_installer_value(path, variables, library_root)).resolve()
        root = files.path(self._work)
        if not resolved.is_relative_to(root) or resolved == root:
            raise CoreError(diagnostic('forge_installation.installer.output.escapes.its.working.directory'))
        checksum = resolve_installer_value(digest, variables, library_root)
        if not re.fullmatch(r"[0-9a-fA-F]{40}", checksum):
            raise CoreError(diagnostic('forge_installation.installer.output.sha.is.invalid'))
        return Artifact("", self._work + "/" + resolved.relative_to(root).as_posix(), digests=(Digest("sha1", checksum),))

    def _extract_embedded(self, libraries: tuple[Artifact, ...], generated: set[str], cancellation: Cancellation) -> None:
        files = self._app.get("files", FileManager)
        config = self._app.get("config", CoreConfig)
        for artifact in libraries:
            suffix = artifact.relative_path.split("/libraries/", 1)[1]
            stage = replace(artifact, relative_path=self._work + "/libraries/" + suffix)
            if stage.relative_path in generated or stage.url or files.exists(stage.relative_path):
                continue
            for prefix in ("maven/", "cache/"):
                try:
                    content = files.archive_member(self._archive.relative_path, prefix + suffix, config.installer_archive_bytes)
                except CoreError:
                    continue
                files.write_bytes(stage.relative_path, content, cancellation)
                if stage.digests and not files.verify(stage, cancellation):
                    raise CoreError(diagnostic('forge_installation.embedded.installer.library.failed.verification'))
                break

    def _download_mappings(self, arguments: tuple[str, ...], task_id: str, cancellation: Cancellation) -> bool:
        if "--task" not in arguments or arguments[arguments.index("--task") + 1] != "DOWNLOAD_MOJMAPS":
            return False
        if len(arguments) != 8 or set(arguments[::2]) != {"--task", "--version", "--side", "--output"}:
            return False
        options = dict(zip(arguments[::2], arguments[1::2]))
        if options["--side"] != "client" or options["--version"] != self._plan.minecraft_version:
            raise CoreError(diagnostic('forge_installation.installer.mappings.request.does.not.match'))
        files = self._app.get("files", FileManager)
        destination = Path(options["--output"]).resolve()
        root = files.path(self._work)
        if not destination.is_relative_to(root):
            raise CoreError(diagnostic('forge_installation.installer.mappings.output.escapes.working.directory'))
        entry = object_value(parse_json(self._parent_data).get("downloads"), "Minecraft downloads").get("client_mappings")
        artifact = parse_artifact(entry, self._work + "/" + destination.relative_to(root).as_posix())
        self._app.get("downloads", DownloadManager).execute(DownloadBatch((artifact,), "Mojang mappings"), task_id, cancellation)
        return True
