from Core.application.diagnostics import diagnostic
import re

from urllib.parse import quote, urlsplit

from Core.application.contracts import CoreError, InstallRequest, UnsupportedInstaller
from Core.installation.installer_contracts import InstallerPlan, InstallerProcessor
from Core.game.metadata import maven_path, object_value, parse_artifact, parse_json, string_value
from Core.application.settings import CoreConfig
from Core.application.storage import checked_relative, safe_identifier


def installer_url(request: InstallRequest, config: CoreConfig) -> str:
    if request.loader == "Forge":
        coordinate = f"net.minecraftforge:forge:{request.minecraft_version}-{request.loader_version}:installer"
        base = config.forge_maven_url
    elif request.loader == "NeoForge":
        coordinate = f"net.neoforged:neoforge:{request.loader_version}:installer"
        base = config.neoforge_maven_url
    else:
        raise CoreError(diagnostic('installer_metadata.an.official.forge.family.installer.was'))
    return f"{base.rstrip('/')}/{quote(maven_path(coordinate), safe='/')}"


def checked_installer_url(url: str, config: CoreConfig) -> str:
    target = urlsplit(url)
    test_origins = tuple(urlsplit(base) for base in (config.forge_maven_url, config.neoforge_maven_url))
    loopback = target.hostname in ("127.0.0.1", "localhost", "::1") and any(target.scheme == origin.scheme and target.netloc == origin.netloc for origin in test_origins)
    if (target.scheme != "https" and not loopback) or not target.hostname or target.username or target.password or target.fragment:
        raise CoreError(diagnostic('installer_metadata.installer.dependencies.require.trusted.https.urls'))
    return url


def parse_installer(install_data: bytes, profile_data: bytes, request: InstallRequest, config: CoreConfig) -> InstallerPlan:
    install = parse_json(install_data)
    if install.get("spec") != 1 or "versionInfo" in install:
        raise UnsupportedInstaller(diagnostic('installer_metadata.this.legacy.or.unknown.installer.format'))
    minecraft = string_value(install.get("minecraft"), "installer.minecraft")
    version = safe_identifier(string_value(install.get("version"), "installer.version"))
    profile = parse_json(profile_data)
    if minecraft != request.minecraft_version or profile.get("inheritsFrom") != minecraft or profile.get("id") != version:
        raise CoreError(diagnostic('installer_metadata.installer.profile.does.not.match.the'))
    libraries = []
    for raw in install.get("libraries", []):
        library = object_value(raw, "installer.library")
        name = string_value(library.get("name"), "installer.library.name")
        entry = object_value(object_value(library.get("downloads"), "installer.library.downloads").get("artifact"), "installer.library.artifact")
        relative = entry.get("path") or maven_path(name)
        artifact = parse_artifact(entry, f"{config.cores_directory}/{config.cache_directory}/libraries/{relative}", local=True)
        if artifact.url:
            checked_installer_url(artifact.url, config)
        libraries.append(artifact)
    data = []
    for name, entry in object_value(install.get("data", {}), "installer.data").items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
            raise CoreError(diagnostic('installer_metadata.invalid.installer.data.key'))
        client = object_value(entry, "installer.data.entry").get("client")
        data.append((name, string_value(client, "installer.data.client")))
    processors = []
    for raw in install.get("processors", []):
        entry = object_value(raw, "installer.processor")
        sides = entry.get("sides", ["client", "server"])
        if not isinstance(sides, list) or any(side not in ("client", "server") for side in sides):
            raise CoreError(diagnostic('installer_metadata.invalid.installer.processor.sides'))
        if "client" not in sides:
            continue
        jar = maven_path(string_value(entry.get("jar"), "processor.jar"))
        classpath = entry.get("classpath", [])
        arguments = entry.get("args", [])
        if not isinstance(classpath, list) or not isinstance(arguments, list) or any(not isinstance(value, str) or not value or "\x00" in value for value in (*classpath, *arguments)):
            raise CoreError(diagnostic('installer_metadata.invalid.installer.processor.arguments'))
        outputs = object_value(entry.get("outputs", {}), "processor.outputs")
        processors.append(InstallerProcessor(jar, tuple(maven_path(value) for value in classpath), tuple(arguments), tuple((string_value(key, "output.path"), string_value(value, "output.hash")) for key, value in outputs.items())))
    return InstallerPlan(minecraft, version, profile_data, tuple(libraries), tuple(data), tuple(processors))


def resolve_installer_value(value: str, variables: tuple[tuple[str, str], ...], library_directory: str) -> str:
    if value.startswith("[") and value.endswith("]"):
        return library_directory.rstrip("/") + "/" + maven_path(value[1:-1])
    mapping = dict(variables)
    for name in re.findall(r"\{([^{}]+)\}", value):
        if name not in mapping:
            raise CoreError(diagnostic('installer_metadata.unknown.installer.variable', name))
        value = value.replace("{" + name + "}", mapping[name])
    if "\x00" in value:
        raise CoreError(diagnostic('installer_metadata.installer.argument.contains.nul'))
    return value


def manifest_main_class(data: bytes) -> str:
    text = data.decode("utf-8").replace("\r\n", "\n").replace("\n ", "")
    section = text.split("\n\n", 1)[0]
    for line in section.splitlines():
        if line.lower().startswith("main-class:"):
            name = line.partition(":")[2].strip()
            if re.fullmatch(r"[A-Za-z_$][\w.$]*", name):
                return name
    raise CoreError(diagnostic('installer_metadata.installer.processor.jar.has.no.valid'))
