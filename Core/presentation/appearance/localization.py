import json
from pathlib import Path

from Core.configuration.settings import ASSETS_DIRECTORY, LANGUAGES_DIRECTORY, BUILTIN_LOCALE
from Core.resources.runtime import ResourcePath, embedded


def language_messages(locale):
    if not isinstance(locale, str) or Path(locale).name != locale or any(character in locale for character in '/\\:'):
        raise ValueError(locale)
    messages = json.loads((ASSETS_DIRECTORY / 'locales' / (BUILTIN_LOCALE + '.json')).read_text(encoding='utf-8-sig'))
    paths = (ASSETS_DIRECTORY / 'locales' / (locale + '.json'), LANGUAGES_DIRECTORY / (locale + '.json'))
    for path in paths:
        if embedded() and locale == BUILTIN_LOCALE and not isinstance(path, ResourcePath):
            continue
        if path.is_file():
            entries = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(entries, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in entries.items()):
                raise ValueError(locale)
            messages.update(entries)
    return messages
