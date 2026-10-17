
import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PROJECT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(PROJECT))
import Core.configuration.settings as config

EXE = 'SerpantineLauncher.exe'
MARKER = 'build-info.json'
USER_FILES = {'SerpantineLauncher.json', 'SerpantineThemeHealth.json'}
USER_DIRECTORIES = {'builds', 'Cores', 'libs', 'logs', 'cache', '.venv', 'ThemeWorkbench', 'Docs'}
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '*.tmp', '*.part', '*.pending')


def run(arguments, cwd=PROJECT):
    subprocess.run([str(argument) for argument in arguments], cwd=cwd, check=True)


def validate_output(path):
    path = path.resolve()
    if path == PROJECT or PROJECT.is_relative_to(path):
        raise ValueError('Выходная папка не должна совпадать с проектом или содержать его.')
    protected = ('assets', 'themes', 'theme_sources', 'langs', 'ui', 'Core', 'vendor', '.venv', 'ThemeWorkbench',
                 'Docs', 'builds', 'Cores', 'libs', 'cache', 'logs', 'artifacts')
    if any(path.is_relative_to(PROJECT / name) for name in protected):
        raise ValueError('Выберите отдельную выходную папку вне исходников, данных и artifacts.')
    if path.exists():
        if not path.is_dir() or path.is_symlink():
            raise ValueError('Выходной путь должен быть обычной папкой.')
        marker = path / MARKER
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('builder') != 'serpantine-nuitka':
            raise ValueError('В выходной папке уже есть чужие файлы. Выберите другой --output.')
    return path


def dependencies(skip_install):
    if not skip_install:
        run([sys.executable, '-m', 'pip', 'install', '-r', PROJECT / 'requirements.txt',
             '-r', PROJECT / 'requirements-build.txt'])
    required = ('Nuitka', 'PySide6', 'working-universal-gui', 'Pillow', 'markdown-it-py')
    versions = {}
    for name in required:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            raise ValueError(f'Не установлена зависимость {name}; запустите без --skip-install.') from None
    nuitka_version = tuple(int(part) for part in versions['Nuitka'].split('.')[:2])
    if nuitka_version < (4, 2):
        raise ValueError('Для этой сборки нужен Nuitka 4.2 или новее.')
    return versions


def prepare_source(source):
    from universal_gui.pack.format import build_pack
    source.mkdir()
    shutil.copy2(PROJECT / 'main.py', source / 'main.py')
    for name in ('application', 'appearance', 'cli', 'configuration', 'content', 'game',
                 'installation', 'network', 'presentation', 'resources', 'startup'):
        shutil.copytree(PROJECT / 'Core' / name, source / 'Core' / name, ignore=IGNORE)
    shutil.copytree(PROJECT / 'ui', source / 'ui', ignore=IGNORE)
    assets = source / 'assets'
    assets.mkdir()
    shutil.copy2(config.APP_ICON, assets / 'icon.ico')
    for name in ('ui-defaults.json', 'diagnostics.json'):
        shutil.copy2(PROJECT / 'assets' / name, assets / name)
    shutil.copytree(PROJECT / 'assets/icons', assets / 'icons', ignore=IGNORE)
    (assets / 'locales').mkdir()
    shutil.copy2(PROJECT / 'assets/locales/en.json', assets / 'locales/en.json')
    shutil.copytree(PROJECT / 'langs', source / 'langs', ignore=IGNORE)
    (assets / 'themes').mkdir()
    (source / 'themes').mkdir()

    build_pack(PROJECT / 'theme_sources/serpantine-night', assets / 'themes/serpantine-night.ugtheme')
    build_pack(PROJECT / 'theme_sources/serpantine-day', assets / 'themes/serpantine-day.ugtheme')
    from Core.build.resources import embed
    inventory = embed(source, source.parent, PROJECT)
    required = {'assets/ui-defaults.json', 'assets/diagnostics.json'}
    if not required.issubset(entry['key'] for entry in inventory):
        raise ValueError('Встроенная база не содержит обязательные реестры приложения.')
    check_clean(source, prepared=True)


def check_clean(folder, prepared=False):
    if any((folder / name).exists() for name in USER_DIRECTORIES):
        raise ValueError('В сборку попали пользовательские или служебные каталоги.')
    for path in folder.rglob('*'):
        if path.name in USER_FILES or path.name == '__pycache__' or path.suffix in ('.pyc', '.pending', '.part'):
            raise ValueError('В сборку попал лишний файл: ' + str(path.relative_to(folder)))
    for name in ('ui', 'assets', 'universal_gui/data', 'universal_gui/qml'):
        if (folder / name).exists():
            raise ValueError('База должна быть встроена, а не лежать рядом: ' + name)
    if (folder / 'langs/en.json').exists() or list((folder / 'themes').glob('serpantine-*.ugtheme')):
        raise ValueError('Встроенный язык или тема попали во внешнюю папку.')
    required = ('langs/ru.json', '_launcher_embedded.py', '_launcher_qt_resources.py') if prepared else ('langs/ru.json',)
    for name in required:
        if not (folder / name).is_file():
            raise ValueError('Не хватает ресурса приложения: ' + name)


def command(source, work, options):
    version = config.APP_VERSION.lstrip('Vv') + '.0'
    arguments = [sys.executable, '-m', 'nuitka', '--mode=standalone', '--enable-plugin=pyside6',
        '--include-qt-plugins=sensible,qml', '--include-package=universal_gui',
        '--include-module=_launcher_embedded', '--include-module=_launcher_qt_resources',
        '--include-package=Core',
        '--windows-console-mode=attach', '--windows-icon-from-ico=' + str(work / 'icon.ico'),
        '--product-name=' + config.APP_NAME, '--file-description=' + config.APP_NAME,
        '--file-version=' + version, '--product-version=' + version,
        '--output-filename=' + EXE, '--output-dir=' + str(work / 'compiled'),
        '--report=' + str(work / 'compilation-report.xml'), '--assume-yes-for-downloads',
        '--jobs=' + str(options.jobs), '--lto=no']
    for name in ('langs',):
        arguments.append('--include-data-dir=' + str(source / name) + '=' + name)
    from Core.build.qt_runtime import exclusions
    qt_options, removed = exclusions()
    arguments.extend(qt_options)
    (work / 'qt-runtime-exclusions.json').write_text(json.dumps(removed, indent=2), encoding='utf-8')
    if options.compiler == 'msvc':
        arguments.append('--msvc=latest')
    elif options.compiler == 'mingw64':
        arguments.append('--mingw64')
    arguments.append(str(source / 'main.py'))
    return arguments


def publish(distribution, output):

    distribution = distribution.resolve()
    build_root = (PROJECT / 'artifacts/nuitka').resolve()
    if not distribution.is_relative_to(build_root) or not (distribution / EXE).is_file():
        raise ValueError('Неверная папка результата Nuitka.')
    output = validate_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if output.exists():
        backup_root = PROJECT / 'artifacts/previous-releases' if output.parent == PROJECT else output.parent
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / (output.name + '.previous-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        if backup.resolve().parent != backup_root.resolve() or backup.exists():
            raise ValueError('Неверный путь резервной копии прежней сборки.')
        output.rename(backup)
    try:
        shutil.move(str(distribution), str(output))
    except Exception:
        if backup is not None and not output.exists():
            backup.rename(output)
        raise
    if backup is not None:
        print('Прежняя сборка сохранена:', backup, flush=True)


def main():
    parser = argparse.ArgumentParser(description='Сборка чистого Launcher EXE через Nuitka')
    parser.add_argument('--output', type=Path, default=PROJECT / 'лаунчер')
    parser.add_argument('--compiler', choices=('auto', 'msvc', 'mingw64'), default='auto')
    parser.add_argument('--jobs', type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument('--skip-install', action='store_true')
    parser.add_argument('--prepare-only', action='store_true', help='Подготовить файлы и команду без компиляции EXE')
    options = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Этот сборщик создаёт Windows EXE; запустите его на Windows.')
    if options.jobs < 1:
        parser.error('--jobs должен быть положительным.')
    output = validate_output(options.output)
    versions = dependencies(options.skip_install) if not options.prepare_only else None

    work_root = PROJECT / 'artifacts/nuitka'
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='build-', dir=work_root)).resolve()
    source = work / 'source'
    prepare_source(source)
    arguments = command(source, work, options)
    (work / 'build-command.json').write_text(json.dumps(arguments, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Подготовлены чистые исходники и ресурсы:', source, flush=True)
    if options.prepare_only:
        print('Команда Nuitka:', work / 'build-command.json', flush=True)
        print('EXE не компилировался. Настройки и игровые файлы не скопированы.', flush=True)
        return 0
    print('Начинается компиляция. Первый запуск может скачать C-компилятор.', flush=True)
    run(arguments, cwd=source)
    distributions = list((work / 'compiled').glob('*.dist'))
    if len(distributions) != 1 or not (distributions[0] / EXE).is_file():
        raise ValueError('Nuitka не создал ожидаемую standalone-папку с EXE.')
    return finalize_release(distributions[0], work, output, versions)


def finalize_release(distribution, work, output, versions):
    check_clean(distribution)
    if any(distribution.glob('qt6web*.dll')) or any(distribution.glob('qt6quick3d*.dll')):
        raise ValueError('В сборку попали неиспользуемые библиотеки браузера или 3D.')
    (distribution / 'themes').mkdir(exist_ok=True)
    if not list((distribution / 'PySide6').rglob('qwindows.dll')):
        raise ValueError('В standalone-сборке отсутствует Qt platform plugin qwindows.dll.')

    result = subprocess.run([str(distribution / EXE), '--version'], cwd=work,
        capture_output=True, text=True, timeout=60, check=True)
    if config.APP_VERSION not in result.stdout:
        raise ValueError('EXE не прошёл проверку --version: ' + result.stdout + result.stderr)
    result = subprocess.run([str(distribution / EXE), '--verify-embedded-resources'], cwd=work,
        capture_output=True, text=True, timeout=60, check=True)
    verified = json.loads(result.stdout)
    inventory = json.loads((work / 'embedded-resources.json').read_text(encoding='utf-8'))
    if verified.get('embedded') is not True or verified.get('verified_files') != len(inventory):
        raise ValueError('EXE не прошёл проверку встроенных ресурсов.')

    for flags, label in (((), 'gpu'), (('--software', '--day', '--live'), 'software-live'),
                         (('--custom',), 'custom-theme')):
        result = subprocess.run([str(distribution / EXE), '--verify-release-ui', *flags], cwd=work,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
        (work / ('ui-check-' + label + '.stderr.log')).write_text(result.stderr, encoding='utf-8')
        (work / ('ui-check-' + label + '.json')).write_text(result.stdout, encoding='utf-8')
        if result.returncode:
            raise ValueError('EXE не прошёл проверку интерфейса: ' + label + '\n' + result.stderr[-3000:])
        report = json.loads(result.stdout)
        if report.get('warnings') or report.get('embedded') is not True:
            raise ValueError('EXE не прошёл проверку интерфейса: ' + label)
    check_clean(distribution)
    (distribution / MARKER).write_text(json.dumps(dict(builder='serpantine-nuitka',
        app_version=config.APP_VERSION, built_at=datetime.now(timezone.utc).isoformat(),
        dependencies=versions, user_state_included=False, embedded_base=True,
        embedded_resource_files=len(inventory)), ensure_ascii=False, indent=2), encoding='utf-8')
    publish(distribution, output)
    print('Готово:', output / EXE, flush=True)
    print('Переносите всю папку лаунчера. Настройки появятся только при его использовании.', flush=True)
    print('Отчёт компиляции:', work / 'compilation-report.xml', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('Сборка не завершена: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
