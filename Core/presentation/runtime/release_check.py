
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from contextlib import closing


def run(arguments):
    import Core.configuration.settings as config
    from PySide6.QtCore import QObject, QMetaObject, qInstallMessageHandler
    from Core.resources.runtime import embedded, copy_resource_tree
    from universal_gui.contracts import Request
    from universal_gui.pack.format import build_pack, ThemePack, PackLimits
    from Core.presentation.runtime.startup import create_loading_application
    software = '--software' in arguments
    theme = 'serpantine-day' if '--day' in arguments else 'serpantine-night'
    live = '--live' in arguments
    custom = '--custom' in arguments
    warnings = []
    origin = float(arguments[arguments.index('--timing-origin') + 1]) if '--timing-origin' in arguments else None
    phase = ['startup']
    qInstallMessageHandler(lambda kind, context, message: warnings.append(phase[0] + ': ' + message))
    with TemporaryDirectory(prefix='serpantine-release-check-') as directory:
        root = Path(directory) / 'Games' / 'ланучер'
        root.mkdir(parents=True)
        config.THEMES_DIRECTORY = root / 'themes'
        config.THEMES_DIRECTORY.mkdir()
        if custom:
            source = root / 'theme-source'
            source.mkdir()
            pack_path = config.ASSETS_DIRECTORY / 'themes' / (theme + '.ugtheme')
            if not pack_path.exists():
                pack_path = config.THEMES_DIRECTORY / (theme + '.ugtheme')
            with closing(ThemePack(pack_path, PackLimits(4194304, 67108864, 10000))) as pack:
                for key in pack.keys():
                    target = source / key
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(pack.read(key))
            copy_resource_tree(config.UI_DIRECTORY, source / 'views')
            manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
            theme = manifest['id'] = 'release-custom'
            manifest['icon'] = 'assets/cores.png'
            manifest['launcher'] = {'api': 1, 'viewsRoot': 'views'}
            (source / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            build_pack(source, config.THEMES_DIRECTORY / (theme + '.ugtheme'))

        def factory():
            from dataclasses import replace
            from Core.application.bootstrap import create_core_config
            from Core.application.runtime import CoreRuntime
            from Core.content.catalogue import CatalogueManager
            from Core.application.application_contracts import CatalogueSource
            from Core.application.application_contracts import BuildRecord
            from Core.application.application_store import ApplicationStore
            import zipfile
            index = root / 'libs/assets/indexes/fixture.json'
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text('{}')
            (root / 'libs/assets/objects').mkdir()
            (root / 'libs/libraries').mkdir()
            (root / 'libs' / config.CORE_RESOURCES_METADATA_FILENAME).write_text(json.dumps({
                'schema': 1, 'asset_index_path': 'libs/assets/indexes/fixture.json'}))
            backend = CoreRuntime(replace(create_core_config(), root=root, available_memory_mb=8192))
            backend.app.get('catalogue', CatalogueManager).fetch_source = lambda loader, cancellation: CatalogueSource(loader)
            backend.app.get('application_store', ApplicationStore).write_build(BuildRecord('manual', 'Manual', '1.21.1', 'Fabric', '0.16.14'), create=True)
            build = root / 'builds/manual'
            for folder in ('Mods', 'ResourcePacks', 'ShaderPacks'):
                (build / folder).mkdir()
            with zipfile.ZipFile(build / 'Mods/мод.jar', 'w') as archive:
                archive.writestr('fabric.mod.json', json.dumps(dict(schemaVersion=1, id='manual', name='Manual mod', version='1.0')))
            (build / 'Mods/disabled.jar.disabled').write_bytes(b'unknown archive')
            (build / 'ResourcePacks/текстуры.zip').write_bytes(b'pack')
            (build / 'ShaderPacks/шейдер.zip').write_bytes(b'pack')
            return backend

        began = time.perf_counter()
        app, boot = create_loading_application(preview=not live, state_root=root, theme=theme,
            hardware_acceleration=not software, backend_factory=factory)

        def wait(predicate, timeout=30):
            deadline = time.monotonic() + timeout
            while not predicate() and time.monotonic() < deadline:
                app._application.processEvents()
                time.sleep(.002)
            assert predicate(), (boot.phase, boot.error, warnings[-10:])

        def walk(item):
            yield item
            for child in item.childItems():
                yield from walk(child)

        def named(name):
            for item in walk(window.contentItem()):
                if item.objectName() == name:
                    return item

        try:
            window = app.runtime.router.request(Request('windows', 'instance', 'main'))
            wait(lambda: named('launcher.startup.screen') is not None or boot.phase == 'failed')
            viewport = named('launcher.startup.viewport')
            screen = named('launcher.startup.screen')
            assert viewport is not None and screen is not None, boot.error
            radius = viewport.property('bottomRadius')
            assert radius > 0
            assert viewport.property('roundedClipActive') == (not software)
            assert screen.property('bottomLeftRadius') == screen.property('bottomRightRadius') == radius
            wait(lambda: boot.phase in ('shown', 'failed'))
            assert boot.phase == 'shown', boot.error
            ready_ms = (time.perf_counter() - began) * 1000
            launch_ready_ms = (time.perf_counter() - origin) * 1000 if origin is not None else None
            session = boot.session
            if custom:
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QImage
                assert theme in session.themeIcons
                assert not QImage(QUrl(session.themeIcons[theme]).toLocalFile()).isNull()
            window = app.runtime.router.request(Request('windows', 'instance', 'main'))
            api = window.rendererInterface().graphicsApi().name
            assert api == ('Software' if software else 'Direct3D11'), api
            assert not viewport.property('roundedClipActive')
            for page in ('styles', 'settings', 'cores', 'profile', 'builds'):
                phase[0] = page
                session.command('navigate', page)
                wait(lambda: named('page.' + page) is not None and app.runtime._incubation.controller.incubatingObjectCount() == 0)
                until = time.monotonic() + .12
                wait(lambda: time.monotonic() > until)
            wait(lambda: app.runtime._incubation.controller.incubatingObjectCount() == 0)
            main = window.property('mainContent')
            phase[0] = 'navigation-popup'
            assert main is not None
            assert QMetaObject.invokeMethod(main, 'openNavigationSettings')
            wait(lambda: named('navigation.settings.form') is not None)
            popup = named('navigation.settings.loader')
            assert popup.property('popupReady')
            assert QMetaObject.invokeMethod(popup, 'close')
            wait(lambda: not popup.property('popupVisible'))
            button = named('builds.create')
            phase[0] = 'create-popup'
            assert button is not None and QMetaObject.invokeMethod(button, 'clicked')
            creation = named('builds.create.loader')
            wait(lambda: creation.property('popupVisible'))
            assert QMetaObject.invokeMethod(creation, 'close')
            wait(lambda: not creation.property('popupVisible'))
            phase[0] = 'build-filters'
            filters = named('builds.filter.loader')
            assert filters is not None and QMetaObject.invokeMethod(filters, 'open')
            wait(lambda: filters.property('popupVisible'))
            filter_popup = filters.property('item')
            assert filter_popup.objectName() == 'builds.filter.popup'
            search = named('builds.filter.id')
            assert search is not None
            search.setProperty('text', 'manual')
            assert QMetaObject.invokeMethod(search, 'textEdited')
            assert named('page.builds').property('filterId') == 'manual'
            assert QMetaObject.invokeMethod(filters, 'close')
            wait(lambda: not filters.property('popupVisible'))
            if live:
                phase[0] = 'live-editor-files'
                from threading import Event
                from Core.application.tasks import TaskManager
                release = Event()
                def blocked(task, cancellation):
                    while not release.is_set():
                        cancellation.wait(.02)
                tasks = session._core.app.get('tasks', TaskManager)
                blockers = [tasks.submit('blocked network fixture', blocked) for _ in range(3)]
                wait(lambda: len([task for task in tasks.snapshots() if task.task_id in blockers and task.state == 'running']) == 3)
                editors = app.runtime.router._departments['editor_workspace']
                session.command('edit', 'manual')
                wait(lambda: 'manual' in editors._pages)
                page = editors._pages['manual']
                page.setProperty('section', 'mods')
                wait(lambda: session.editorModsModel('manual').count == 2)
                wait(lambda: any(item.objectName() == 'editor.mod.Mods/мод.jar' for item in walk(page)))
                wait(lambda: app.runtime._incubation.controller.incubatingObjectCount() == 0)
                assert next(item for item in session.editorMods('manual') if item['enabled'])['title'] == 'Manual mod'
                external = root / 'builds/manual/Mods/external.jar'
                external.write_bytes(b'external mod')
                wait(lambda: session.editorModsModel('manual').count == 3)
                wait(lambda: 'manual' not in session._editor_scans.values())
                external.unlink()
                wait(lambda: session.editorModsModel('manual').count == 2)
                for section, path in (('packs', 'ResourcePacks/текстуры.zip'), ('shaders', 'ShaderPacks/шейдер.zip')):
                    page.setProperty('section', section)
                    wait(lambda: any(item.objectName() == 'content.installed.' + path for item in walk(page)))
                    wait(lambda: app.runtime._incubation.controller.incubatingObjectCount() == 0)
                editors.command('close_window', editors._group_of('manual'), '')
                wait(lambda: not editors.windowKeys)
                release.set()
                if '--io-server' in arguments:
                    import hashlib
                    from Core.application.contracts import Artifact, Digest, DownloadBatch
                    from Core.network.downloads import DownloadManager
                    url = arguments[arguments.index('--io-server') + 1]
                    payload = b'asset-integrity-' * 8192
                    artifact = Artifact(url + '/resume', 'libs/fixture-download', len(payload), (Digest('sha256', hashlib.sha256(payload).hexdigest()),))
                    task = session._core.app.get('downloads', DownloadManager).submit(DownloadBatch((artifact,)))
                    wait(lambda: next(item for item in tasks.snapshots() if item.task_id == task).state in ('completed', 'failed'), timeout=30)
                    assert tasks.wait(task, 1) == (artifact.relative_path,)
                    assert (root / artifact.relative_path).read_bytes() == payload
                    assert not list(root.rglob('*.part'))
            if not live:
                phase[0] = 'editor'
                editors = app.runtime.router._departments['editor_workspace']
                session.command('edit', 'quiet_valley')
                wait(lambda: 'quiet_valley' in editors._pages)
                page = editors._pages['quiet_valley']
                for section in ('java', 'mods', 'packs', 'shaders', 'files', 'logs', 'worlds', 'general'):
                    page.setProperty('section', section)
                    until = time.monotonic() + .08
                    wait(lambda: time.monotonic() > until)
                    wait(lambda: app.runtime._incubation.controller.incubatingObjectCount() == 0)
                group = editors._group_of('quiet_valley')
                for kind in ('mod', 'resourcepack', 'shader'):
                    editors.openContent('quiet_valley', 'fixture-' + kind, kind, group)
                    wait(lambda: 'quiet_valley:' + kind + ':fixture-' + kind in editors._pages)
                    wait(lambda: app.runtime._incubation.controller.incubatingObjectCount() == 0)
                editors.command('close_window', group, '')
                wait(lambda: not editors.windowKeys)
            wait(lambda: app.runtime._incubation.controller.incubatingObjectCount() == 0)
            report = dict(embedded=embedded(), live=live, custom=custom, theme=theme,
                startup_corners_match_window=True, startup_mask_unloaded=True,
                graphics_api=api, ready_ms=round(ready_ms, 2),
                process_to_ready_ms=round(launch_ready_ms, 2) if launch_ready_ms is not None else None, trace=boot.trace)
        finally:
            phase[0] = 'closing'
            app.close()
        report['warnings'] = warnings
        print(json.dumps(report, ensure_ascii=False), flush=True)
        assert not warnings, warnings
    return 0
