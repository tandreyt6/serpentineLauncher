from universal_gui.pack.format import validate_key
from Core.application.diagnostics import diagnostic


def theme_icon_key(manifest):
    key = manifest.get('icon', '')
    if not isinstance(key, str):
        raise ValueError(diagnostic('theme.icon.invalid.key'))
    if key:
        validate_key(key)
    return key
