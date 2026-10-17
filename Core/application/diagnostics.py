from functools import lru_cache
import json

from Core.configuration.settings import ASSETS_DIRECTORY


@lru_cache(maxsize=1)
def messages():
    return json.loads((ASSETS_DIRECTORY / 'diagnostics.json').read_text(encoding='utf-8'))


def diagnostic(key, *arguments):
    template = messages()[key]
    return template.format(*arguments) if arguments else template
