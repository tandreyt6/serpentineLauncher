
from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib
from Core.build.source_policy import clean_file


def replace(source, before, after, expected=1):
    content = source.read_text(encoding='utf-8')
    if content.count(before) != expected:
        raise ValueError('Unexpected UGF source; cannot adapt embedded paths: ' + str(source))
    source.write_text(content.replace(before, after), encoding='utf-8')


def embed(source, work, project):
    framework = Path(next(iter(find_spec('universal_gui').submodule_search_locations)))
    shutil.copytree(framework, source / 'universal_gui', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    files = {}
    roots = ((source / 'ui', 'ui'), (source / 'assets', 'assets'),
             (source / 'universal_gui/data', 'universal_gui/data'),
             (source / 'universal_gui/qml', 'universal_gui/qml'),
             (project / 'theme_sources/serpantine-night', 'builtin-themes/serpantine-night'),
             (project / 'theme_sources/serpantine-day', 'builtin-themes/serpantine-day'))
    for root, prefix in roots:
        for path in sorted(root.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.tmp', '.pending'):


                if prefix.startswith('builtin-themes/') and path.relative_to(root).as_posix() != 'bootloader.qml' and not path.relative_to(root).as_posix().startswith('boot/'):
                    continue
                if path.is_symlink():
                    raise ValueError('Cannot embed symlink: ' + str(path))
                files[prefix + '/' + path.relative_to(root).as_posix()] = path
    if any(key.startswith('assets/locales/') and key != 'assets/locales/en.json' for key in files):
        raise ValueError('Only English belongs in the immutable base')
    root = ET.Element('RCC')
    collection = ET.SubElement(root, 'qresource', prefix='/serpantine')
    for key, path in sorted(files.items()):
        ET.SubElement(collection, 'file', alias=key).text = str(path)
    qrc = work / 'base.qrc'
    ET.ElementTree(root).write(qrc, encoding='utf-8', xml_declaration=True)
    rcc = Path(sys.executable).parent / 'pyside6-rcc.exe'
    if not rcc.is_file():
        raise ValueError('Missing resource compiler: ' + str(rcc))
    subprocess.run([str(rcc), str(qrc), '-o', str(source / '_launcher_qt_resources.py')], check=True)
    clean_file(source / '_launcher_qt_resources.py')

    inventory = []
    with (source / '_launcher_embedded.py').open('w', encoding='utf-8') as stream:
        stream.write('FILES = {\n')
        for key, path in sorted(files.items()):
            data = path.read_bytes()
            stream.write(repr(key) + ': ' + repr(zlib.compress(data, 9)) + ',\n')
            inventory.append(dict(key=key, size=len(data), sha256=sha256(data).hexdigest()))
        stream.write('}\n')
        stream.write('SIZES = ' + repr({entry['key']: entry['size'] for entry in inventory}) + '\n')
    (work / 'embedded-resources.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')


    ugf = source / 'universal_gui'
    replace(ugf / 'runtime.py', 'PACKAGE_ROOT = Path(__file__).resolve().parent',
            'from Core.resources.runtime import resource_root, resource_url\nPACKAGE_ROOT = resource_root("universal_gui", Path(__file__).resolve().parent)')
    replace(ugf / 'runtime.py', 'QUrl.fromLocalFile(str(scene.resolve()))', 'QUrl(resource_url(scene))')
    replace(ugf / 'application.py', 'from universal_gui.runtime import GuiRuntime',
            'from universal_gui.runtime import GuiRuntime\nfrom Core.resources.runtime import scene_path')
    replace(ugf / 'application.py', 'Path(scene).resolve()', 'scene_path(scene)', expected=2)
    replace(ugf / 'services/pages.py', 'from PySide6.QtCore import QUrl',
            'from PySide6.QtCore import QUrl\nfrom Core.resources.runtime import scene_path, resource_url')
    replace(ugf / 'services/pages.py', 'QUrl.fromLocalFile(self._pages[key]).toString()',
            'resource_url(scene_path(self._pages[key]))')
    for relative, kind, count in (('qt/workspace.py', 'tab', 2), ('qt/docking.py', 'panel', 1)):
        path = ugf / relative
        content = path.read_text(encoding='utf-8')
        path.write_text('from Core.resources.runtime import is_local_qml_url\n' + content, encoding='utf-8')
        replace(path, 'QUrl(' + kind + '.source).isLocalFile()', 'is_local_qml_url(' + kind + '.source)', expected=count)
    path = ugf / 'qt/software_image.py'
    path.write_text('from Core.resources.runtime import image_path\n' + path.read_text(encoding='utf-8'), encoding='utf-8')
    replace(path, 'source.toLocalFile() if source.isLocalFile() else source.toString()', 'image_path(source)')
    replace(ugf / 'qt/windows.py', 'from pathlib import Path',
            'from pathlib import Path\nfrom Core.resources.runtime import resource_root, resource_url')
    replace(ugf / 'qt/windows.py', 'Path(__file__).resolve().parents[1] / "qml"',
            'resource_root("universal_gui", Path(__file__).resolve().parents[1]) / "qml"')
    for expression in ('QUrl.fromLocalFile(str(scene))', 'QUrl.fromLocalFile(self._definitions[payload])', 'QUrl.fromLocalFile(payload.scene)'):
        argument = {'QUrl.fromLocalFile(str(scene))':'scene',
                    'QUrl.fromLocalFile(self._definitions[payload])':'scene_path(self._definitions[payload])',
                    'QUrl.fromLocalFile(payload.scene)':'scene_path(payload.scene)'}[expression]
        replace(ugf / 'qt/windows.py', expression, 'QUrl(resource_url(' + argument + '))')
    replace(ugf / 'qt/windows.py', 'resource_root, resource_url', 'resource_root, resource_url, scene_path')
    replace(ugf / 'services/themes.py', 'import json', 'import json\nfrom Core.resources.runtime import ResourcePath')
    replace(ugf / 'services/themes.py', 'self._themes: dict[str, dict] = {}',
            'self._themes: dict[str, dict] = {}\n        self._protected = set()')
    replace(ugf / 'services/themes.py', 'self._validate_manifest(manifest)',
            'self._validate_manifest(manifest)\n        if manifest["id"] in self._protected and not isinstance(path, ResourcePath):\n            raise ValueError("Compiled built-in themes cannot be replaced")')
    replace(ugf / 'services/themes.py', 'self._themes[pack_id] = manifest',
            'self._themes[pack_id] = manifest\n        if isinstance(path, ResourcePath):\n            self._protected.add(pack_id)')


    inputs = work / 'embedded-input'
    inputs.mkdir()
    for relative in ('ui', 'assets', 'universal_gui/data', 'universal_gui/qml'):
        path = source / relative
        target = inputs / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))

    shutil.copy2(inputs / 'assets/icon.ico', work / 'icon.ico')
    print('Встроены ресурсы базы:', len(inventory), flush=True)
    return inventory
