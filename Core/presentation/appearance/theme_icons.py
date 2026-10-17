import json
from zlib import error as CompressionError

from Core.appearance.theme_metadata import theme_icon_key
from Core.application.diagnostics import diagnostic
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImageReader
from universal_gui.contracts import AssetQuery, Diagnostic, Request


def load_theme_icons(router, errors=None):
    icons = {}
    for identity in router.request(Request('themes', 'available')):
        try:
            manifest = json.loads(router.request(Request('resources', 'read', AssetQuery(identity, 'manifest.json'))).content)
            key = theme_icon_key(manifest)
            if key:
                url = router.request(Request('resources', 'native_url', AssetQuery(identity, key)))
                if not QImageReader(QUrl(url).toLocalFile()).canRead():
                    raise ValueError(diagnostic('theme.icon.unsupported'))
                icons[identity] = url
        except (OSError, ValueError, KeyError, TypeError, CompressionError) as error:
            if errors is not None:
                errors[identity] = str(error)
            router.request(Request('diagnostics', 'record', Diagnostic('WARNING', 'theme.icon_failed', f'{identity}: {error}')))
    return icons
