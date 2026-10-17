from Core.application.diagnostics import diagnostic
import json
import platform
import re
import shlex

from dataclasses import replace
from typing import Any
from urllib.parse import quote

from Core.application.contracts import Argument, Artifact, AssetIndex, CoreError, Digest, Library, LoggingSpec, PlatformSpec, Rule, VersionEntry, VersionProfile
from Core.application.settings import CoreConfig
from Core.application.storage import checked_relative


def host_platform(features: tuple[tuple[str, bool], ...] = ()) -> PlatformSpec:
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "osx"}.get(platform.system(), platform.system().lower())
    machine = platform.machine().lower()
    architecture = "x86_64" if machine == "amd64" else machine
    return PlatformSpec(system, architecture, platform.version(), "64" if machine in ("amd64", "x86_64", "aarch64", "arm64") else "32", features)


def object_value(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CoreError(diagnostic('metadata.expected.metadata.object', name))
    return value


def string_value(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise CoreError(diagnostic('metadata.expected.nonempty.metadata.string', name))
    return value


def parse_json(data: bytes) -> dict[str, Any]:
    return object_value(json.loads(data), "document")


def parse_rules(value: object) -> tuple[Rule, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise CoreError(diagnostic('metadata.rules.must.be.an.array'))
    result: list[Rule] = []
    for entry in value:
        rule = object_value(entry, "rule")
        action = rule.get("action")
        if action not in ("allow", "disallow"):
            raise CoreError(diagnostic('metadata.unknown.rule.action'))
        os_rule = object_value(rule.get("os", {}), "rule.os")
        features = object_value(rule.get("features", {}), "rule.features")
        if any(not isinstance(expected, bool) for expected in features.values()):
            raise CoreError(diagnostic('metadata.rule.feature.values.must.be.booleans'))
        result.append(Rule(action, os_rule.get("name", ""), os_rule.get("arch", ""), os_rule.get("version", ""), tuple(features.items())))
    return tuple(result)


def allowed(rules: tuple[Rule, ...] | None, target: PlatformSpec) -> bool:
    if rules is None:
        return True
    result = False
    features = dict(target.features)
    for rule in rules:
        if rule.os_name and rule.os_name != target.os_name:
            continue
        if rule.architecture and re.search(rule.architecture, target.architecture) is None:
            continue
        if rule.os_version and re.search(rule.os_version, target.os_version) is None:
            continue
        if any(features.get(name, False) != expected for name, expected in rule.features):
            continue
        result = rule.action == "allow"
    return result


def maven_path(coordinate: str) -> str:
    identifier, _, extension = coordinate.partition("@")
    parts = identifier.split(":")
    if len(parts) not in (3, 4) or not all(parts):
        raise CoreError(diagnostic('metadata.invalid.maven.coordinate'))
    group, artifact, version = parts[:3]
    classifier = f"-{parts[3]}" if len(parts) == 4 else ""
    path = f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}{classifier}.{extension or 'jar'}"
    checked_relative(path)
    return path


def parse_artifact(value: object, destination: str, local: bool = False) -> Artifact:
    entry = object_value(value, "artifact")
    url = "" if local and entry.get("url") == "" else string_value(entry.get("url"), "artifact.url")
    size = entry.get("size")
    if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 0):
        raise CoreError(diagnostic('metadata.invalid.artifact.size'))
    digests = tuple(Digest(algorithm, string_value(entry[algorithm], algorithm)) for algorithm in ("sha1", "sha256", "sha512") if algorithm in entry)
    checked_relative(destination)
    return Artifact(url, destination, size, digests)


def parse_arguments(value: object) -> tuple[Argument, ...]:
    if not isinstance(value, list):
        raise CoreError(diagnostic('metadata.arguments.must.be.an.array'))
    result: list[Argument] = []
    for entry in value:
        if isinstance(entry, str):
            result.append(Argument((entry,)))
            continue
        argument = object_value(entry, "argument")
        values = argument.get("value")
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise CoreError(diagnostic('metadata.invalid.argument.values'))
        result.append(Argument(tuple(values), parse_rules(argument.get("rules"))))
    return tuple(result)


def parse_profile(data: dict[str, Any], config: CoreConfig) -> VersionProfile:
    version_id = string_value(data.get("id"), "version.id")
    checked_relative(version_id)
    downloads = object_value(data.get("downloads", {}), "downloads")
    client = parse_artifact(downloads["client"], f"{config.cores_directory}/{config.cache_directory}/versions/{version_id}/{version_id}.jar") if "client" in downloads else None
    library_root = f"{config.cores_directory}/{config.cache_directory}" if data.get("inheritsFrom") else config.libs_directory
    libraries: list[Library] = []
    for raw_library in data.get("libraries", []):
        entry = object_value(raw_library, "library")
        name = string_value(entry.get("name"), "library.name")
        library_downloads = object_value(entry.get("downloads", {}), "library.downloads")
        artifact_entry = library_downloads.get("artifact")
        artifact = None
        if artifact_entry:
            relative = object_value(artifact_entry, "library.artifact").get("path") or maven_path(name)
            artifact = parse_artifact(artifact_entry, f"{library_root}/libraries/{relative}", local=True)
        elif "downloads" not in entry:
            path = maven_path(name)
            base = entry.get("url") or config.library_cdn
            artifact = Artifact(f"{base.rstrip('/')}/{quote(path, safe='/')}", f"{library_root}/libraries/{path}")
        natives: list[tuple[str, Artifact]] = []
        for classifier, native in object_value(library_downloads.get("classifiers", {}), "library.classifiers").items():
            native_entry = object_value(native, "native")
            native_path = native_entry.get("path") or maven_path(f"{name}:{classifier}")
            natives.append((classifier, parse_artifact(native_entry, f"{library_root}/libraries/{native_path}")))
        classifiers = tuple(object_value(entry.get("natives", {}), "library.natives").items())
        extract = object_value(entry.get("extract", {}), "library.extract")
        excludes = tuple(extract.get("exclude", []))
        if any(not isinstance(prefix, str) for prefix in excludes):
            raise CoreError(diagnostic('metadata.invalid.native.excludes'))
        libraries.append(Library(name, artifact, tuple(natives), classifiers, parse_rules(entry.get("rules")), ("META-INF/", *excludes)))
    arguments = object_value(data.get("arguments", {}), "arguments")
    jvm = parse_arguments(arguments.get("jvm", []))
    game = parse_arguments(arguments.get("game", []))
    if "minecraftArguments" in data:
        game = tuple(Argument((argument,)) for argument in shlex.split(string_value(data["minecraftArguments"], "minecraftArguments"), posix=True))
    index = None
    if "assetIndex" in data:
        index_entry = object_value(data["assetIndex"], "assetIndex")
        index_id = string_value(index_entry.get("id"), "assetIndex.id")
        index = AssetIndex(index_id, parse_artifact(index_entry, f"{config.libs_directory}/assets/indexes/{index_id}.json"))
    logging_spec = None
    logging_client = object_value(data.get("logging", {}), "logging").get("client")
    if logging_client:
        logging_entry = object_value(logging_client, "logging.client")
        file_entry = object_value(logging_entry.get("file"), "logging.file")
        logging_id = string_value(file_entry.get("id"), "logging.file.id")
        logging_spec = LoggingSpec(string_value(logging_entry.get("argument"), "logging.argument"), parse_artifact(file_entry, f"{config.libs_directory}/assets/log_configs/{logging_id}"))
    java = object_value(data.get("javaVersion", {}), "javaVersion").get("majorVersion")
    if java is not None and (not isinstance(java, int) or java < 1):
        raise CoreError(diagnostic('metadata.invalid.java.version'))
    return VersionProfile(version_id, data.get("mainClass", ""), data.get("type", ""), client, tuple(libraries), jvm, game, index, java, data.get("inheritsFrom", ""), version_id if client else "", logging_spec)


def library_key(library: Library) -> str:
    identifier, _, extension = library.name.partition("@")
    parts = identifier.split(":")
    return ":".join((*parts[:2], *(parts[3:]))) + "@" + (extension or "jar")


def merge_profiles(parent: VersionProfile, child: VersionProfile) -> VersionProfile:
    if child.parent_id and child.parent_id != parent.version_id:
        raise CoreError(diagnostic('metadata.loader.profile.references.unexpected.parent'))
    libraries = {library_key(library): library for library in parent.libraries}
    libraries.update((library_key(library), library) for library in child.libraries)
    return replace(child, main_class=child.main_class or parent.main_class, version_type=child.version_type or parent.version_type, client=child.client or parent.client, client_version=child.client_version or parent.client_version, libraries=tuple(libraries.values()), jvm_arguments=parent.jvm_arguments + child.jvm_arguments, game_arguments=parent.game_arguments + child.game_arguments, asset_index=child.asset_index or parent.asset_index, java_major=child.java_major or parent.java_major, logging=child.logging or parent.logging)


def profile_artifacts(profile: VersionProfile, target: PlatformSpec) -> tuple[Artifact, ...]:
    if not profile.client:
        raise CoreError(diagnostic('metadata.profile.has.no.client.download'))
    artifacts = [profile.client]
    for library in profile.libraries:
        if not allowed(library.rules, target):
            continue
        if library.artifact:
            artifacts.append(library.artifact)
        native = native_artifact(library, target)
        if native:
            artifacts.append(native)
    if profile.asset_index:
        artifacts.append(profile.asset_index.artifact)
    if profile.logging:
        artifacts.append(profile.logging.artifact)
    return tuple(artifacts)


def native_artifact(library: Library, target: PlatformSpec) -> Artifact | None:
    classifier = dict(library.classifiers).get(target.os_name)
    if classifier is None:
        return None
    classifier = classifier.replace("${arch}", target.bits)
    native = dict(library.natives).get(classifier)
    if native is None:
        raise CoreError(diagnostic('metadata.missing.native.classifier.download'))
    return native


def manifest_entries(data: dict[str, Any], config: CoreConfig) -> tuple[VersionEntry, ...]:
    entries: list[VersionEntry] = []
    for value in data.get("versions", []):
        entry = object_value(value, "manifest.version")
        version = string_value(entry.get("id"), "manifest.version.id")
        checked_relative(version)
        artifact = parse_artifact(entry, f"{config.cores_directory}/{config.cache_directory}/versions/{version}/{version}.json")
        entries.append(VersionEntry(version, entry.get("type", ""), entry.get("releaseTime", ""), artifact))
    return tuple(entries)


def asset_artifacts(data: dict[str, Any], config: CoreConfig) -> tuple[Artifact, ...]:
    if data.get("virtual") or data.get("map_to_resources"):
        raise CoreError(diagnostic('metadata.legacy.virtual.resource.mapped.assets.require'))
    unique: dict[str, Artifact] = {}
    for value in object_value(data.get("objects"), "assets.objects").values():
        entry = object_value(value, "asset")
        digest = string_value(entry.get("hash"), "asset.hash")
        if len(digest) != 40 or any(character not in "0123456789abcdef" for character in digest):
            raise CoreError(diagnostic('metadata.invalid.asset.sha'))
        size = entry.get("size")
        if not isinstance(size, int) or size < 0:
            raise CoreError(diagnostic('metadata.invalid.asset.size'))
        unique[digest] = Artifact(f"{config.asset_cdn.rstrip('/')}/{digest[:2]}/{digest}", f"{config.libs_directory}/assets/objects/{digest[:2]}/{digest}", size, (Digest("sha1", digest),))
    return tuple(unique.values())
