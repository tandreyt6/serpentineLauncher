from dataclasses import dataclass

from Core.application.contracts import Artifact


@dataclass(frozen=True)
class InstallerProcessor:
    jar: str
    classpath: tuple[str, ...]
    arguments: tuple[str, ...]
    outputs: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class InstallerPlan:
    minecraft_version: str
    version_id: str
    profile: bytes
    libraries: tuple[Artifact, ...]
    data: tuple[tuple[str, str], ...]
    processors: tuple[InstallerProcessor, ...]


@dataclass(frozen=True)
class InstallerResult:
    profile: bytes
    artifacts: tuple[Artifact, ...]
