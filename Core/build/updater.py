from pathlib import Path
import os
import subprocess
import tempfile
import sys


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
        subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
            '/reference:System.Web.Extensions.dll', '/reference:System.Windows.Forms.dll',
            '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
            '/out:' + str(target), str(Path(project) / 'Core/updates/Updater.cs'), str(metadata)], check=True)
    return target


if __name__ == '__main__':
    import argparse
    project = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Build the standalone Windows updater')
    parser.add_argument('--output', type=Path, default=project / 'artifacts/updater')
    options = parser.parse_args()
    print(build_updater(project, options.output))
