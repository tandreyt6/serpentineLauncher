from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Digest:
    algorithm: Literal["sha1", "sha256", "sha512"]
    value: str


@dataclass(frozen=True)
class Artifact:
    url: str
    relative_path: str
    size: int | None = None
    digests: tuple[Digest, ...] = ()
