from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import re
import stat
from zipfile import ZipFile, ZIP_DEFLATED

from Core.application.diagnostics import diagnostic

EXECUTABLE = 'SerpantineLauncher.exe'
MANIFEST = 'launcher-update.json'
PLATFORM = 'windows-x64'
MAXIMUM_ARCHIVE = 1073741824
MAXIMUM_CONTENT = 3221225472
MAXIMUM_FILES = 40000
PROTECTED = frozenset(name.casefold() for name in ('builds', 'Cores', 'libs', 'logs', 'cache', 'themes', 'theme_sources', '.git', '.venv', '.idea', 'BetaThemes', 'ThemeWorkbench', 'SerpantineLauncher.json', 'SerpantineThemeHealth.json', 'catalog.json'))


def version(value):
    match = re.fullmatch(r'[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(diagnostic('updates.invalid_version'))
    return tuple(map(int, match.groups()))


def asset_name(value):
    return 'serpentineLauncher-' + '.'.join(map(str, version(value))) + '-' + PLATFORM + '.zip'


def relative(value):
    path = PurePosixPath(value) if isinstance(value, str) else PurePosixPath('/')
    if not value or path.is_absolute() or path.as_posix() != value or any(part in ('', '.', '..') or part.endswith(('.', ' ')) or ':' in part or '\\' in part or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part) for part in path.parts) or path.parts[0].casefold() in PROTECTED:
        raise ValueError(diagnostic('updates.unsafe_path'))
    return path


def digest(path):
    with path.open('rb') as stream:
        return sha256_file(stream)


def sha256_file(stream):
    result = sha256()
    while data := stream.read(262144):
        result.update(data)
    return result.hexdigest()


def validate_manifest(data, expected):
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('platform') != PLATFORM or version(data.get('version')) != version(expected) or data.get('executable') != EXECUTABLE or not isinstance(data.get('files'), dict) or not 1 <= len(data['files']) <= MAXIMUM_FILES:
        raise ValueError(diagnostic('updates.invalid_package'))
    seen = set()
    total = 0
    for name, item in data['files'].items():
        relative(name)
        if name.casefold() in seen or name.casefold() == MANIFEST.casefold() or not isinstance(item, dict) or type(item.get('size')) is not int or item['size'] < 0 or not re.fullmatch(r'[0-9a-f]{64}', item.get('sha256', '')):
            raise ValueError(diagnostic('updates.invalid_package'))
        seen.add(name.casefold())
        total += item['size']
    if EXECUTABLE not in data['files'] or total > MAXIMUM_CONTENT:
        raise ValueError(diagnostic('updates.invalid_package'))
    return data


def extract(archive, folder, expected, cancellation):
    with ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) > MAXIMUM_FILES + 1 or any(item.is_dir() or stat.S_ISLNK(item.external_attr >> 16) for item in entries) or len({item.filename.casefold() for item in entries}) != len(entries):
            raise ValueError(diagnostic('updates.invalid_package'))
        info = source.getinfo(MANIFEST)
        if info.file_size > 16777216:
            raise ValueError(diagnostic('updates.invalid_package'))
        manifest = validate_manifest(json.loads(source.read(info)), expected)
        if {item.filename for item in entries} != set(manifest['files']) | {MANIFEST}:
            raise ValueError(diagnostic('updates.invalid_package'))
        for item in entries:
            cancellation.check()
            target = folder.joinpath(*relative(item.filename).parts)
            declared = manifest['files'].get(item.filename)
            if declared is not None and item.file_size != declared['size']:
                raise ValueError(diagnostic('updates.invalid_package'))
            target.parent.mkdir(parents=True, exist_ok=True)
            checksum = sha256()
            with source.open(item) as content, target.open('xb') as output:
                while chunk := content.read(262144):
                    cancellation.check()
                    checksum.update(chunk)
                    output.write(chunk)
            if declared is not None and checksum.hexdigest() != declared['sha256']:
                raise ValueError(diagnostic('updates.checksum'))
    return manifest


def build_release(distribution, output, release_version):
    distribution = Path(distribution).resolve()
    files = {}
    for path in sorted(distribution.rglob('*')):
        if path.is_symlink():
            raise ValueError(diagnostic('updates.unsafe_path'))
        if path.is_file() and path.name != MANIFEST:
            name = path.relative_to(distribution).as_posix()
            relative(name)
            files[name] = {'size': path.stat().st_size, 'sha256': digest(path)}
    manifest = validate_manifest(dict(schema=1, version=release_version, platform=PLATFORM, executable=EXECUTABLE, files=files), release_version)
    (distribution / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / asset_name(release_version)
    temporary = target.with_suffix('.zip.tmp')
    with ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(set(files) | {MANIFEST}):
            archive.write(distribution / name, name)
    if temporary.stat().st_size > MAXIMUM_ARCHIVE:
        raise ValueError(diagnostic('updates.invalid_package'))
    temporary.replace(target)
    (target.with_suffix('.zip.sha256')).write_text(digest(target) + '  ' + target.name + '\n', encoding='ascii')
    return target
