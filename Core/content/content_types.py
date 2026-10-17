from dataclasses import dataclass

from Core.application.contracts import CoreError


@dataclass(frozen=True, slots=True)
class ContentType:
    key: str
    directory: str
    extension: str
    loaders: tuple[str, ...]


CONTENT_TYPES = (
    ContentType('mod', 'mods', '.jar', ('fabric', 'forge', 'neoforge', 'quilt')),
    ContentType('resourcepack', 'resourcepacks', '.zip', ('minecraft', 'vanilla', 'optifine')),
    ContentType('shader', 'shaderpacks', '.zip', ('iris', 'optifine', 'canvas')),
)


def content_type(key: str) -> ContentType:
    found = next((item for item in CONTENT_TYPES if item.key == key), None)
    if found is None:
        raise CoreError('Unknown Modrinth content type: ' + key)
    return found
