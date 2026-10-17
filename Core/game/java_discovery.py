import os
import shutil
from pathlib import Path


def registry_java_homes():
    if os.name != 'nt':
        return ()
    import winreg
    homes = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            for name in ('Java Runtime Environment', 'Java Development Kit', 'JRE', 'JDK'):
                try:
                    with winreg.OpenKey(hive, 'SOFTWARE\\JavaSoft\\' + name, 0, winreg.KEY_READ | view) as root:
                        for index in range(winreg.QueryInfoKey(root)[0]):
                            try:
                                with winreg.OpenKey(root, winreg.EnumKey(root, index)) as version:
                                    value = winreg.QueryValueEx(version, 'JavaHome')[0]
                                    if isinstance(value, str) and value.strip():
                                        homes.append(Path(os.path.expandvars(value)))
                            except OSError:
                                continue
                except OSError:
                    continue
    return tuple(homes)


def java_candidates():
    executable = 'java.exe' if os.name == 'nt' else 'java'
    candidates = []
    command = shutil.which('java')
    if command:
        candidates.append(Path(command))
    candidates.extend(Path(directory) / executable for directory in os.get_exec_path() if directory)
    homes = [Path(os.environ[key].strip('"')) for key in ('JAVA_HOME', 'JDK_HOME', 'JRE_HOME') if os.environ.get(key)]
    homes.extend(registry_java_homes())
    roots = [Path.home() / '.jdks']
    if os.name == 'nt':
        vendors = ('Java', 'Eclipse Adoptium', 'AdoptOpenJDK', 'Microsoft', 'Amazon Corretto', 'BellSoft', 'Zulu', 'Semeru')
        for key in ('ProgramFiles', 'ProgramW6432', 'ProgramFiles(x86)'):
            if os.environ.get(key):
                roots.extend(Path(os.environ[key]) / vendor for vendor in vendors)
        if os.environ.get('LOCALAPPDATA'):
            roots.extend(Path(os.environ['LOCALAPPDATA']) / 'Programs' / vendor for vendor in vendors)
    else:
        roots.extend((Path('/usr/lib/jvm'), Path('/usr/java'), Path('/opt/java'), Path('/Library/Java/JavaVirtualMachines'), Path.home() / 'Library/Java/JavaVirtualMachines'))
    for root in roots:
        homes.append(root)
        try:
            homes.extend(child for child in root.iterdir() if child.is_dir())
        except OSError:
            continue
    for home in homes:
        candidates.extend((home / 'bin' / executable, home / 'Contents/Home/bin' / executable))
    found = []
    seen = set()
    for candidate in candidates:
        try:
            path = candidate.resolve()
            if path not in seen and path.is_file():
                seen.add(path)
                found.append(path)
        except OSError:
            continue
    return tuple(found)
