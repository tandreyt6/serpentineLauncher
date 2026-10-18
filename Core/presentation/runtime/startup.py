from Core.application.diagnostics import diagnostic

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication
from universal_gui.application import GuiApplication
from universal_gui.contracts import AppearanceQuery, LocaleCatalog, Request
from universal_gui.pack.format import ThemePack, PackLimits, build_pack, validate_key
from universal_gui.runtime import PACKAGE_ROOT
from universal_gui.qt.visuals import VisualHost

import Core.configuration.settings as config
from Core.resources.runtime import ResourcePath, embedded, register_qt_resources, resource_root, resource_url
from Core.application.diagnostics import messages
from Core.appearance.theme_health import ThemeHealth, ThemeHealthDriver
from Core.presentation.runtime.platform_identity import configure_application_identity

LIMITS = PackLimits(4194304, 67108864, 10000)
PROTECTED = ('office', 'slate', 'serpantine-night', 'serpantine-day')


def theme_paths(identities=None):

    found = {}
    for directory in (config.ASSETS_DIRECTORY / 'themes', config.THEMES_DIRECTORY):
        paths = (sorted(directory.glob('*.ugtheme')) + sorted(directory.glob('*.ugtheme' + config.THEME_UPDATE_SUFFIX))
                 if identities is None else [path for suffix in ('.ugtheme', '.ugtheme' + config.THEME_UPDATE_SUFFIX)
                                            for identity in identities
                                            for path in [directory / (identity + suffix), *sorted(directory.glob(identity + '~*' + suffix))]
                                            if path.is_file()])
        for path in paths:
            try:
                with_pack = ThemePack(path, LIMITS)
                try:
                    manifest = json.loads(with_pack.read('manifest.json'))
                    if embedded() and manifest['id'] in PROTECTED and not isinstance(path, ResourcePath):
                        continue
                    found[manifest['id']] = path
                finally:
                    with_pack.close()
            except (OSError, ValueError, KeyError):
                continue
    return found


def prepare_backend(core, preview, factory, instance, activation, selected, paths):

    from Core.application.application_contracts import ApplicationCommand, VisualResourcesRequest
    from Core.application.application import ApplicationManager
    from Core.appearance.appearance_packs import AppearanceFileDriver
    from Core.application.settings import CoreConfig
    from Core.application.tasks import Cancellation, TaskManager
    from Core.appearance.theme_scenes import ThemeSceneDriver, ThemeSceneRequest, ThemeSceneBundle, scene_configuration
    backend = core
    owned = core is None and not preview
    try:
        if owned:
            backend = factory()
        if backend is not None:
            tasks = backend.app.get('tasks', TaskManager)
            task = backend.app.get('application', ApplicationManager).submit(ApplicationCommand('bootstrap', fields=(("prepare_resources", "true"),)))
            try:
                tasks.wait(task)
            finally:
                tasks.release(task)
            from Core.updates.resume import adopt
            adopt(backend)
            if instance is not None:
                from Core.cli.service import CliService
                instance.start(CliService(backend.app, activation).handle)
        elif preview and instance is not None:
            from Core.cli.contracts import CliResponse
            from Core.cli.instance import ipc_failure
            def activate_preview(request):
                if request.action != 'activate':
                    return ipc_failure(request, 'Preview mode supports window activation only')
                activation.set()
                text = json.dumps({'ok': True, 'result': 'Launcher activated'}) if request.format == 'json' else 'Launcher activated'
                return CliResponse(0, text + '\n')
            instance.start(activate_preview)
        settings = backend.app.get('config', CoreConfig) if backend else CoreConfig(config.ROOT)
        files = backend.app.get('appearance_files', AppearanceFileDriver) if backend else AppearanceFileDriver(settings)
        resources = files.prepare(VisualResourcesRequest(config.ASSETS_DIRECTORY, config.LANGUAGES_DIRECTORY,
            config.THEMES_DIRECTORY, config.DEFAULT_THEME, config.THEME_UPDATE_SUFFIX), Cancellation())
        paths = theme_paths()
        driver = ThemeSceneDriver()
        if backend:
            try:
                driver = backend.app.get('theme_scenes', ThemeSceneDriver)
            except KeyError:
                backend.app.register('theme_scenes', driver)
        theme_error = ''
        requested = selected
        while True:
            try:
                pack = ThemePack(paths[selected], LIMITS)
                try:
                    manifest = json.loads(pack.read('manifest.json'))
                    roots = scene_configuration(manifest)
                    contents = tuple((key, pack.read(key)) for key in pack.keys()
                                     if any(root and key.startswith(root + '/') for root in roots))
                finally:
                    pack.close()
                bundle = driver.prepare(ThemeSceneRequest(selected, config.UI_DIRECTORY, PACKAGE_ROOT / 'qml',
                    json.dumps(manifest).encode(), contents), Cancellation()) if contents else ThemeSceneBundle(selected, None, '')
                break
            except Exception as error:
                if selected == config.DEFAULT_THEME:
                    raise
                theme_error = str(error)
                selected = config.DEFAULT_THEME
        return SimpleNamespace(core=backend, resources=resources, paths=paths, bundle=bundle, driver=driver,
                               settings=settings, theme_error=theme_error, requested_theme=requested)
    except Exception:
        if owned and backend is not None:
            backend.close()
        raise


class LauncherStartup(QObject):
    changed = Signal()
    sourceChanged = Signal()
    readyRequested = Signal()
    sessionReady = Signal(object)

    def __init__(self, preview, core, factory, instance, activation, theme, hardware_acceleration, state_root):
        super().__init__()
        self.preview, self.core, self.factory = preview, core, factory
        self.instance, self.activation = instance, activation
        self._owns_core = core is None and not preview
        self._phase, self._error, self._source = 'preparing', '', ''
        self.closed, self.first_seen = False, False
        self._content_ready = False
        self.session = None
        self.images = None
        self._image_items = ()
        self._ui_signature = None
        self._ui_frames = 0
        self._ui_frame_requested = 0.0
        self._ui_items = {}
        self.future = None
        self.started = time.monotonic()
        self.trace = []
        self._temporary = TemporaryDirectory(prefix='serpantine-boot-')
        self.directory = Path(self._temporary.name)
        state = state_root / config.APPLICATION_STATE_FILENAME
        settings = {}
        if not preview and state.is_file():
            with state.open('rb') as stream:
                data = stream.read(4194305)
            if len(data) > 4194304:
                raise ValueError(diagnostic('startup.application.state.exceeds.size.limit'))
            settings = json.loads(data).get('settings', {})
        self.acceleration = hardware_acceleration if hardware_acceleration is not None else settings.get('hardwareAcceleration', True)
        self.locale = settings.get('locale', config.DEFAULT_LOCALE)
        if type(self.acceleration) is not bool:
            self.acceleration = True
        if not isinstance(self.locale, str):
            self.locale = config.DEFAULT_LOCALE
        self.health_driver = ThemeHealthDriver(state_root)
        self.health = ThemeHealth() if preview else self.health_driver.read().recover_interrupted(PROTECTED)
        selected = theme or settings.get('theme', config.DEFAULT_THEME)
        if not isinstance(selected, str) or not selected or not all(character.isalnum() or character in '_-' for character in selected):
            selected = config.DEFAULT_THEME
        if selected in dict(self.health.failures):
            selected = config.DEFAULT_THEME
        self.paths = theme_paths(tuple(dict.fromkeys((config.DEFAULT_THEME, selected))))
        if selected not in self.paths:
            self.paths = theme_paths()
        self.selected = selected if selected in self.paths and selected not in dict(self.health.failures) else config.DEFAULT_THEME
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='launcher-boot')
        self.timer = QTimer(self)
        self.timer.setInterval(config.STARTUP_POLL_INTERVAL_MS)
        self.timer.timeout.connect(self.poll)
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(config.STARTUP_POLL_INTERVAL_MS)
        self.ui_timer.timeout.connect(self.inspect_ui)
        self.activation_timer = QTimer(self)
        self.activation_timer.setInterval(config.STARTUP_ACTIVATION_INTERVAL_MS)
        self.activation_timer.timeout.connect(self.check_activation)
        self.load_boot(self.selected)

    def mark(self, event, **details):
        self.trace.append(dict(event=event, ms=round((time.monotonic()-self.started)*1000, 2), **details))

    def check_activation(self):
        if not self.closed and self.session is not None and self.activation.is_set():
            self.activation.clear()
            self.session.windowAction.emit('show')

    phase = Property(str, lambda self: self._phase, notify=changed)
    error = Property(str, lambda self: self._error, notify=changed)
    source = Property(str, lambda self: self._source, notify=sourceChanged)
    style = Property('QVariantMap', lambda self: self.palette, notify=changed)
    preparingText = Property(str, lambda self: self.texts['startup.preparing'], notify=changed)
    readyText = Property(str, lambda self: self.texts['startup.ready'], notify=changed)
    contentReady = Property(bool, lambda self: self._content_ready, notify=changed)

    def save_health(self):
        if not self.preview:
            self.health_driver.write(self.health)

    def load_boot(self, selected):
        self.selected = selected
        self.health = ThemeHealth(self.health.failures, selected if selected not in PROTECTED else '')
        self.save_health()
        pack = ThemePack(self.paths[selected], LIMITS)
        source = self.directory / selected
        source.mkdir(exist_ok=True)
        try:
            manifest = json.loads(pack.read('manifest.json'))
            keys = ['bootloader.qml'] + [key for key in pack.keys() if key.startswith('boot/')]
            caption = dict(manifest.get('tokens', {}))
            rules = [rule for rule in manifest.get('rules', [])
                     if rule.get('tag') == 'app.main' or rule.get('type') == 'AppWindow']
            for rule in rules:
                caption.update(rule.get('values', {}))
            keys += [caption[key] for key in ('minimizeIconKey', 'maximizeIconKey', 'restoreIconKey', 'closeIconKey') if caption.get(key)]
            for key in dict.fromkeys(keys):
                validate_key(key)
                target = source / key
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(pack.read(key))
        except Exception as error:
            pack.close()
            if selected == config.DEFAULT_THEME:
                raise
            self.quarantine(selected, str(error))
            return self.load_boot(config.DEFAULT_THEME)
        finally:
            pack.close()
        boot_manifest = dict(manifest)
        boot_manifest['rules'] = [{k: v for k, v in rule.items() if k != 'visual'} for rule in rules if rule.get('values')]
        (source / 'manifest.json').write_text(json.dumps(boot_manifest), encoding='utf-8')
        packs = self.directory / 'packs'
        packs.mkdir(exist_ok=True)
        self.bootstrap_pack = packs / ('boot-' + selected + '.ugtheme')
        build_pack(source, self.bootstrap_pack)
        self.palette = dict(manifest.get('tokens', {}))
        builtin_boot = resource_root('builtin-themes', config.ROOT / 'theme_sources') / selected / 'bootloader.qml'
        self._source = resource_url(builtin_boot if embedded() and selected in PROTECTED else source / 'bootloader.qml')
        self.mark('boot-resources-read', theme=selected, keys=list(dict.fromkeys(keys)))
        if hasattr(self, 'app'):
            if self.session is None:
                self.app.runtime.router.request(Request('themes', 'reload', self.bootstrap_pack))
            self.app.runtime.router.request(Request('themes', 'select', selected))
            self.resolve_palette()
            self.changed.emit()
            self.sourceChanged.emit()

    def resolve_palette(self):
        self.palette = json.loads(self.app.runtime.router.request(Request('themes', 'resolve', AppearanceQuery('AppWindow', 'app.main'))).encoded)

    def quarantine(self, theme, message):
        failures = dict(self.health.failures)
        if theme not in PROTECTED:
            failures[theme] = message[:config.THEME_FAILURE_DETAIL_LENGTH]
        self.health = ThemeHealth(tuple(failures.items()))
        self.save_health()

    def attach(self, app):
        self.app = app
        self._incubation_interval = app.runtime._incubation.timer.interval()
        app.runtime._incubation.timer.setInterval(config.STARTUP_INCUBATION_INTERVAL_MS)
        if self.preview and self.activation is not None:
            self.activation_timer.start()
        self.resolve_palette()
        self.changed.emit()
        self.mark('graphics-engine-ready')
        app.runtime.engine.warnings.connect(self.qml_warnings)
        app.runtime.router.register('launcher_startup', self)

    @Slot()
    def bootLoaded(self):
        self.mark('theme-boot-created', session_exists=self.session is not None)
        if self._phase == 'ready':
            QTimer.singleShot(0, self.readyRequested.emit)

    @Slot()
    def first_frame(self):
        if self.closed:
            return
        if self._ui_signature is not None and self._phase == 'preparing':
            self._ui_frames += 1
        if self.first_seen:
            return
        window = self.app.runtime.router.request(Request('windows', 'instance', 'main'))
        if not window.property('bootSceneLoaded'):
            return
        self.first_seen = True
        self.mark('boot-first-frame', core_exists=self.core is not None, session_exists=self.session is not None)
        QTimer.singleShot(0, self.begin)

    def begin(self):
        if self.closed:
            return
        self.mark('backend-prepare-started')
        self.future = self.executor.submit(prepare_backend, self.core, self.preview, self.factory,
            self.instance if not self.core else None, self.activation, self.selected, self.paths)
        self.timer.start()

    def poll(self):
        if self.closed or not self.future.done():
            return
        self.timer.stop()
        try:
            self.prepared = self.future.result()
            self.core = self.prepared.core
            if self.prepared.theme_error and self.selected == self.prepared.requested_theme:
                self.quarantine(self.selected, self.prepared.theme_error)
                self.load_boot(config.DEFAULT_THEME)
            if self.prepared.bundle.theme_id != self.selected:
                self.begin()
                return
            self.mark('backend-prepared')
            self.mounts = iter(self.prepared.paths.items())
            self.app.runtime.router.request(Request('themes', 'preview_enable'))
            self.mount_next()
        except Exception as error:
            self.fail(str(error))

    def mount_next(self):
        if self.closed:
            return
        entry = next(self.mounts, None)
        if entry is None:
            self.app.runtime.router.request(Request('themes', 'select', self.selected))
            QTimer.singleShot(4, self.install)
            return
        identity, path = entry
        try:
            self.app.runtime.router.request(Request('themes', 'reload', path))
        except Exception as error:
            if identity == self.selected:
                self.bootFailed(str(error))
                if self._phase != 'failed':
                    self.begin()
                return
        QTimer.singleShot(4, self.mount_next)

    def install(self):
        if self.closed:
            return
        try:
            from Core.presentation.appearance.appearance_packs import AppearancePackManager
            from Core.application.application_contracts import AppearanceScanRequest
            from Core.presentation.runtime.bootstrap import attach_session
            runtime = self.app.runtime
            for language in self.prepared.resources.languages:
                runtime.router.request(Request('localization', 'register', LocaleCatalog(language.id, language.entries)))
            runtime.router.request(Request('localization', 'select', self.locale))
            packs = AppearancePackManager(None, self.prepared.settings,
                AppearanceScanRequest('languages', (config.ASSETS_DIRECTORY / 'locales', config.LANGUAGES_DIRECTORY)),
                AppearanceScanRequest('themes', (config.ASSETS_DIRECTORY / 'themes', config.THEMES_DIRECTORY), config.THEME_UPDATE_SUFFIX),
                self.core.app if self.core else None, scene_driver=self.prepared.driver)
            _, self.session = attach_session(self.app, self.preview, self.core, packs,
                self.prepared.resources, self.health, self.prepared.bundle, bootstrapped=True)
            runtime.router.request(Request('lifecycle', 'attach'))
            if self.activation:
                self.activation.clear()
            self.mark('session-created')
            self.sessionReady.emit(self.session)
        except Exception as error:
            self.fail(str(error))

    @Slot()
    def uiLoaded(self):
        if self._phase == 'shown':
            return
        self.clear_ui_checks()
        self._ui_items = {}
        self.mark('main-ui-created')
        self.ui_timer.start()

    def clear_ui_checks(self):
        for expression in self.images or ():
            expression.deleteLater()
        self.images = None
        self._image_items = ()
        self._ui_signature = None
        self._ui_frames = 0
        self._ui_frame_requested = 0.0

    def inspect_ui(self):
        try:
            runtime = self.app.runtime
            if runtime._incubation.controller.incubatingObjectCount() or self.session is None:
                self._ui_signature = None
                self._ui_frames = 0
                return
            if runtime.router.request(Request('visuals', 'pending')):
                self._ui_signature = None
                self._ui_frames = 0
                return
            scenes = runtime.router.request(Request('theme_scenes', 'status'))
            if scenes.theme_id != self.session.theme:
                return
            window = runtime.router.request(Request('windows', 'instance', 'main'))
            main = window.property('mainContent')
            if main is None:
                return
            if main is not None and main.property('startupReady') is False:
                return
            def walk(item):
                yield item
                for child in item.childItems():
                    yield from walk(child)
            items = tuple(walk(main))
            self._ui_items.update((id(item), item) for item in items)
            deadline = time.monotonic() + config.STARTUP_VISUAL_BUDGET_MS / 1000
            for item in items:
                if isinstance(item, VisualHost) and item._ready and item._state is not None and item._source and item._item is None:
                    item._rebuild()
                    self._ui_signature = None
                    self._ui_frames = 0
                    if time.monotonic() >= deadline:
                        return
            image_items = tuple(item for item in items if item.inherits('QQuickImage') or item.inherits('QQuickLoader'))
            image_items += tuple(item for item in main.findChildren(QObject) if item.inherits('QQuickFontLoader'))
            self._ui_items.update((id(item), item) for item in items + image_items)
            if self.images is None or image_items != self._image_items:
                for expression in self.images or ():
                    expression.deleteLater()
                self._image_items = image_items
                self.images = [QQmlExpression(QQmlEngine.contextForObject(item), item, 'status === 2', self)
                               for item in image_items]
            if any(expression.evaluate()[0] for expression in self.images):
                self._ui_signature = None
                self._ui_frames = 0
                return
            if not self.preview and not self.session._restored:
                return
            signature = tuple((item, item.width(), item.height()) for item in items)
            if signature != self._ui_signature:
                self._ui_signature = signature
                self._ui_frames = 0
                self._ui_frame_requested = 0.0
            if self._ui_frames < 2:
                now = time.monotonic()
                if self._ui_frame_requested and (now - self._ui_frame_requested) * 1000 >= config.STARTUP_FRAME_WAIT_MS:
                    # A covered window may render without presenting a frame to the desktop.
                    frames = self._ui_frames
                    image = window.grabWindow()
                    if not image.isNull() and self._ui_frames == frames:
                        self._ui_frames += 1
                    self._ui_frame_requested = now
                elif not self._ui_frame_requested:
                    self._ui_frame_requested = now
                window.update()
                return
            self.ui_timer.stop()
            runtime._incubation.timer.setInterval(self._incubation_interval)
            self._content_ready = True
            self.mark('main-ui-ready', rendered_frames=self._ui_frames, items=len(items), resources=len(image_items))
            self._phase = 'ready'
            self.clear_ui_checks()
            self.changed.emit()
            self.readyRequested.emit()
        except Exception as error:
            self.fail(str(error))

    def qml_warnings(self, errors):
        if self.closed or self._phase == 'shown':
            return
        root = QUrl.fromLocalFile(str(self.directory)).toString()
        owned = [error.toString() for error in errors if error.url().toString().startswith(root)]
        if owned:
            failed_theme = self.selected
            QTimer.singleShot(0, lambda: self.bootFailed('\n'.join(owned)) if failed_theme == self.selected else None)

    @Slot(str)
    def bootFailed(self, reason):
        if self.closed:
            return
        if self.selected == config.DEFAULT_THEME:
            self.fail(reason)
            return
        if self.session is not None:
            self.ui_timer.stop()
            self._phase = 'preparing'
            self._content_ready = False
            self.clear_ui_checks()
            self.changed.emit()
            scenes = self.app.runtime.router._departments['theme_scenes']
            scenes.rejectTheme(self.selected, reason)
            self.health = ThemeHealth(tuple(scenes.failedThemes.items()))
        else:
            self.quarantine(self.selected, reason)
        self.load_boot(config.DEFAULT_THEME)
        if self.session is not None:
            self.ui_timer.start()

    def fail(self, reason):
        self._phase, self._error = 'failed', reason
        if hasattr(self, 'app'):
            self.app.runtime._incubation.timer.setInterval(self._incubation_interval)
        self.timer.stop()
        self.ui_timer.stop()
        self.mark('failed', error=reason)
        self.changed.emit()

    @Slot()
    def reveal(self):
        if self._phase == 'ready':
            self._phase = 'revealing'
            self.changed.emit()

    @Slot()
    def finish(self):
        if self._phase == 'revealing':
            self._phase = 'shown'
            self.mark('boot-finished')
            self.changed.emit()
            from Core.updates import resume
            if resume.state is not None:
                from Core.presentation.runtime.quiet_resume import restore
                window = self.app.runtime.router.request(Request('windows', 'instance', 'main'))
                restore(window)
                self.session.command('navigate', resume.state['window'].get('page', 'builds'))
                resume.acknowledge()

    def handle(self, action, payload):
        raise ValueError(action)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.timer.stop()
        self.ui_timer.stop()
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.activation_timer.stop()
        if self._owns_core:
            backend = self.core
            if backend is None and self.future and self.future.done() and not self.future.cancelled():
                try:
                    backend = self.future.result().core
                except Exception:
                    pass
            if backend:
                backend.close()
        if self.health.attempt and self.session is None:
            current = self.health if self.preview else self.health_driver.read()
            self.health = ThemeHealth(current.failures)
            self.save_health()

    def dispose_files(self):
        self._temporary.cleanup()


class LoadingApplication(GuiApplication):
    def close(self):
        try:
            super().close()
        finally:
            if hasattr(self, 'startup'):
                self.startup.close()
                self.startup.dispose_files()


def create_loading_application(preview=False, core=None, instance=None, activation=None, theme='', *, hardware_acceleration=None,
                               state_root=config.ROOT, backend_factory=None):
    register_qt_resources()
    if backend_factory is None:
        def backend_factory():
            from Core.application.bootstrap import create_core_runtime
            return create_core_runtime()
    boot = LauncherStartup(preview, core, backend_factory, instance, activation, theme, hardware_acceleration, state_root)
    locale_paths = (config.ASSETS_DIRECTORY / 'locales' / (boot.locale + '.json'), config.LANGUAGES_DIRECTORY / (boot.locale + '.json'))
    texts = {}
    for path in locale_paths:
        if embedded() and boot.locale == 'en' and not isinstance(path, ResourcePath):
            continue
        if path.is_file():
            texts.update(json.loads(path.read_text(encoding='utf-8-sig')))
    if not all(key in texts for key in ('app.main', 'startup.preparing', 'startup.ready')):
        boot.locale = config.DEFAULT_LOCALE
        texts = json.loads((config.LANGUAGES_DIRECTORY / (boot.locale + '.json')).read_text(encoding='utf-8-sig'))
    boot.texts = texts
    QQuickStyle.setStyle('Basic')
    configure_application_identity(config.APP_ID)
    qt = QGuiApplication.instance() or QApplication([])
    QGuiApplication.setWindowIcon(QIcon(str(config.APP_ICON)))
    qt.setDesktopFileName(config.APP_ID)
    app = LoadingApplication(config.APP_NAME, (boot.directory / 'packs',),
        {'theme.initial': boot.selected, 'locale.initial': config.DEFAULT_LOCALE}, hardware_acceleration=boot.acceleration)
    app.startup = boot
    app.translations(boot.locale, {key: texts[key] for key in ('app.main', 'startup.preparing', 'startup.ready')})
    app.window('main', config.UI_DIRECTORY / 'Window.qml')
    try:
        runtime = app.start(preview=preview, application=qt)
        runtime.router.request(Request('localization', 'select', boot.locale))
        runtime.router.request(Request('themes', 'preview_enable'))
        runtime.engine.rootContext().setContextProperty('Boot', boot)
        runtime.engine.rootContext().setContextProperty('UiDefaults', config.UI_STYLE_DEFAULTS)
        runtime.engine.rootContext().setContextProperty('UiDiagnostics', messages())
        boot.attach(app)
        from Core.updates import resume
        if resume.state is not None and not preview:
            from Core.presentation.runtime.quiet_resume import open_quiet
            open_quiet(app)
        else:
            app.open_window('main')
        runtime.router.request(Request('windows', 'instance', 'main')).frameSwapped.connect(boot.first_frame)
        return app, boot
    except Exception:
        app.close()
        boot.close()
        raise
