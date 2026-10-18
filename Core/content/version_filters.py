from Core.configuration.settings import MINECRAFT_VERSION_FILTERS


def visible_minecraft_versions(versions, types, settings):
    enabled = {category for category, setting, text_key in MINECRAFT_VERSION_FILTERS if settings[setting]}
    if len(enabled) == len(MINECRAFT_VERSION_FILTERS):
        return list(versions)
    return [version for version in versions if version in types and types[version] in enabled]
