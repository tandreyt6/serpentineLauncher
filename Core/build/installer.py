import os
from pathlib import Path
import shutil
import subprocess

from Core.updates.package import asset_name, EXECUTABLE


def compiler():
    configured = shutil.which('ISCC.exe')
    candidates = [Path(configured)] if configured else []
    for key in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA'):
        if os.environ.get(key):
            candidates.append(Path(os.environ[key]) / ('Programs/Inno Setup 6/ISCC.exe' if key == 'LOCALAPPDATA' else 'Inno Setup 6/ISCC.exe'))
    found = next((path for path in candidates if path.is_file()), None)
    if found is None:
        raise ValueError('Install Inno Setup 6 or build with --skip-installer.')
    return found


def build_setup(distribution, output, version):
    distribution = Path(distribution).resolve()
    output = Path(output).resolve()
    if not (distribution / EXECUTABLE).is_file():
        raise ValueError('The standalone launcher executable is missing.')
    output.mkdir(parents=True, exist_ok=True)
    normalized = asset_name(version).removeprefix('serpentineLauncher-').removesuffix('-windows-x64.zip')
    subprocess.run([str(compiler()), '/Qp', '/DSourceDirectory=' + str(distribution), '/DReleaseVersion=' + normalized, '/DOutputDirectory=' + str(output), str(Path(__file__).with_suffix('.iss'))], check=True)
    target = output / ('serpentineLauncher-' + normalized + '-windows-x64-setup.exe')
    if not target.is_file():
        raise ValueError('Inno Setup did not create the expected installer.')
    return target
