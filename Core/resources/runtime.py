
from fnmatch import fnmatchcase
from io import BytesIO, TextIOWrapper
from pathlib import Path
import shutil
import stat
import os
import zlib

try:
    import _launcher_embedded as _bundle
except ModuleNotFoundError as error:
    if error.name != '_launcher_embedded':
        raise
    _bundle = None

_registered = False
_PathBase = type(Path())


def embedded():
    return _bundle is not None


class ResourcePath(_PathBase):

    def __str__(self):
        return super().__str__().replace('\\', '/')

    def _key(self):
        return str(self).removeprefix(':/serpantine/').rstrip('/')

    def resolve(self, strict=False):
        if strict and not self.exists():
            raise FileNotFoundError(str(self))
        return self

    def absolute(self):
        return self

    def is_file(self):
        return self._key() in _bundle.FILES

    def is_dir(self):
        prefix = self._key() + '/'
        return any(key.startswith(prefix) for key in _bundle.FILES)

    def exists(self):
        return self.is_file() or self.is_dir()

    def is_symlink(self):
        return False

    def read_bytes(self):
        try:
            return zlib.decompress(_bundle.FILES[self._key()])
        except KeyError:
            raise FileNotFoundError(str(self)) from None

    def read_text(self, encoding=None, errors=None):
        return self.read_bytes().decode(encoding or 'utf-8', errors or 'strict')

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        if mode not in ('r', 'rb', 'rt'):
            raise PermissionError('Compiled resources are read-only')
        stream = BytesIO(self.read_bytes())
        return stream if mode == 'rb' else TextIOWrapper(stream, encoding=encoding or 'utf-8', errors=errors, newline=newline)

    def stat(self, *, follow_symlinks=True):
        if not self.exists():
            raise FileNotFoundError(str(self))
        return os.stat_result((stat.S_IFREG | 0o444 if self.is_file() else stat.S_IFDIR | 0o555,
                               0, 0, 1, 0, 0, _bundle.SIZES[self._key()] if self.is_file() else 0, 0, 0, 0))

    def iterdir(self):
        if not self.is_dir():
            raise NotADirectoryError(str(self))
        prefix = self._key() + '/'
        names = {key[len(prefix):].split('/')[0] for key in _bundle.FILES if key.startswith(prefix)}
        return iter(self / name for name in sorted(names))

    def glob(self, pattern):
        return (path for path in self.iterdir() if fnmatchcase(path.name, pattern)) if self.is_dir() else iter(())

    def rglob(self, pattern):
        if not self.is_dir():
            return iter(())
        prefix = self._key() + '/'
        names = set()
        for key in _bundle.FILES:
            if key.startswith(prefix):
                parts = key[len(prefix):].split('/')
                names.update('/'.join(parts[:count]) for count in range(1, len(parts)+1))
        return iter(self / name for name in sorted(names) if fnmatchcase(name.split('/')[-1], pattern))


def resource_root(namespace, fallback):
    return ResourcePath(':/serpantine/' + namespace) if embedded() else fallback


def scene_path(path):
    text = str(path).replace('\\', '/')
    if text.startswith(':/serpantine/'):
        return ResourcePath(text)
    return Path(path).resolve()


def register_qt_resources():
    global _registered
    if embedded() and not _registered:
        import _launcher_qt_resources
        _registered = True


def resource_url(path):
    from PySide6.QtCore import QUrl
    if isinstance(path, ResourcePath):
        register_qt_resources()
        return QUrl('qrc' + str(path)).toString()
    return QUrl.fromLocalFile(str(path)).toString()


def is_local_qml_url(source):
    from PySide6.QtCore import QUrl
    url = QUrl(source)
    return url.isLocalFile() or url.scheme() == 'qrc'


def image_path(source):
    if source.scheme() == 'qrc':
        return ':' + source.path()
    return source.toLocalFile() if source.isLocalFile() else source.toString()


def copy_resource_tree(source, destination):
    if not isinstance(source, ResourcePath):
        return shutil.copytree(source, destination)
    destination.mkdir(parents=True)
    for path in source.rglob('*'):
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    return destination


def verify_embedded_resources():

    if not embedded():
        raise RuntimeError('This executable has no compiled base resources')
    register_qt_resources()
    from PySide6.QtCore import QFile, QIODevice
    for key in _bundle.FILES:
        path = ResourcePath(':/serpantine/' + key)
        stream = QFile(str(path))
        if not stream.open(QIODevice.ReadOnly):
            raise RuntimeError('Missing Qt resource: ' + key)
        try:
            if bytes(stream.readAll()) != path.read_bytes():
                raise RuntimeError('Embedded resource mismatch: ' + key)
        finally:
            stream.close()
    return {'embedded': True, 'verified_files': len(_bundle.FILES)}
