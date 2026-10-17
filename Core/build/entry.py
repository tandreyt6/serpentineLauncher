
from pathlib import Path
import subprocess
import sys


def main():
    project = Path(__file__).resolve().parents[2]
    python = project / '.venv/Scripts/python.exe'
    if not python.is_file():
        raise ValueError('Нет .venv/Scripts/python.exe. Установите зависимости проекта.')
    if Path(sys.executable).resolve() != python.resolve() or not sys.flags.utf8_mode:
        return subprocess.call([str(python), '-X', 'utf8', str(project / 'Core/build/build.py'), *sys.argv[1:]], cwd=project)
    from Core.build.pipeline import main as build
    return build()
