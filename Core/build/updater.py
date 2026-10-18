from pathlib import Path
import os
import subprocess
import tempfile
import sys
import json


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Core.updates.version import UPDATER_VERSION, UPDATER_EXECUTABLE


def build_updater(project, output):
    compiler = Path(os.environ['SystemRoot']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not compiler.is_file():
        raise FileNotFoundError(compiler)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / UPDATER_EXECUTABLE
    with tempfile.TemporaryDirectory(prefix='serpentine-updater-build-') as folder:
        metadata = Path(folder) / 'Version.cs'
        metadata.write_text('using System.Reflection;\n[assembly: AssemblyFileVersion("' + UPDATER_VERSION + '.0")]\n[assembly: AssemblyVersion("' + UPDATER_VERSION + '.0")]\n[assembly: AssemblyProduct("Serpentine Launcher Updater")]\n', encoding='utf-8')
        resources = []
        for locale, source in (('en', 'assets/locales/en.json'), ('ru', 'langs/ru.json')):
            entries = json.loads((Path(project) / source).read_text(encoding='utf-8-sig'))
            messages = {key: value for key, value in entries.items() if key.startswith('updates.install.') or key == 'updates.heading'}
            path = Path(folder) / (locale + '.json')
            path.write_text(json.dumps(messages, ensure_ascii=False), encoding='utf-8')
            resources.append('/resource:' + str(path) + ',updater.' + locale + '.json')
        subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
            '/reference:System.Web.Extensions.dll', '/reference:System.Windows.Forms.dll',
            '/reference:System.Drawing.dll',
            '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
            *resources, '/out:' + str(target), str(Path(project) / 'Core/updates/Updater.cs'),
            str(Path(project) / 'Core/updates/UpdateProgress.cs'), str(metadata)], check=True)
    return target


if __name__ == '__main__':
    import argparse
    project = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Build the standalone Windows updater')
    parser.add_argument('--output', type=Path, default=project / 'artifacts/updater')
    options = parser.parse_args()
    print(build_updater(project, options.output))
