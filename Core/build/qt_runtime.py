
from pathlib import Path

QML_ROOTS = ('QtQml', 'QtQuick', 'Qt5Compat/GraphicalEffects', 'QtCore',
             'Qt/labs/animation', 'Qt/labs/folderlistmodel', 'Qt/labs/platform',
             'Qt/labs/qmlmodels', 'Qt/labs/settings', 'Qt/labs/sharedimage')
EXCLUDED_QUICK = ('QtQuick/Scene2D', 'QtQuick/Scene3D', 'QtQuick/VirtualKeyboard')


def supported_qml(relative):
    text = relative.as_posix()
    return any(text == root or text.startswith(root + '/') for root in QML_ROOTS) and not any(
        text == root or text.startswith(root + '/') for root in EXCLUDED_QUICK)


def exclusions():
    from PySide6.QtCore import QLibraryInfo
    directory = Path(QLibraryInfo.path(QLibraryInfo.QmlImportsPath))
    arguments = ['--noinclude-dlls=opengl32sw.dll', '--noinclude-qt-translations',
                 '--noinclude-dlls=PySide6/qt-plugins/imageformats/qpdf.dll']


    for pattern in ('qt63d*', 'qt6quick3d*', 'qt6web*', 'qt6pdf*', 'qt6charts*',
                    'qt6graphs*', 'qt6datavisualization*', 'qt6multimedia*',
                    'qt6spatialaudio*', 'qt6location*', 'qt6positioning*',
                    'qt6sensors*', 'qt6texttospeech*', 'qt6virtualkeyboard*',
                    'qt6remoteobjects*', 'qt6scxml*', 'qt6statemachine*',
                    'qt6labswavefrontmesh*', 'qt6quicktest*', 'qt6test*'):
        arguments.append('--noinclude-dlls=' + pattern + '.dll')
    excluded = []

    def visit(folder):
        for path in sorted(folder.iterdir()):
            relative = path.relative_to(directory)
            text = relative.as_posix()
            if supported_qml(relative):
                if path.is_dir():
                    visit(path)
                continue
            if path.is_dir() and any(root.startswith(text + '/') for root in QML_ROOTS):
                visit(path)
                continue
            name = 'PySide6/qml/' + text + ('/*' if path.is_dir() else '')
            arguments.extend(('--noinclude-dlls=' + name, '--noinclude-data-files=' + name))
            excluded.append(name)
    visit(directory)
    return arguments, excluded
