import subprocess
from dataclasses import dataclass
from pathlib import Path

from Core.application.application_store import ApplicationStore
from Core.application.contracts import CoreError, CoreEvent, JavaSettings
from Core.application.router import EventManager
from Core.game.java import JavaManager, select_java_runtime


@dataclass(frozen=True, slots=True)
class FirstRunSetup:
    java_found: bool


def prepare_first_run(app, cancellation):
    store = app.get('application_store', ApplicationStore)
    with store.lock:
        if store.settings['firstRunComplete']:
            return None
        settings = dict(store.settings)
    java = app.get('java', JavaManager)
    runtime = None
    configured = settings['javaPath']
    if configured:
        try:
            validated = java.validate_settings(JavaSettings(Path(configured), int(settings['memoryMin']), int(settings['memoryMax'])))
            runtime = java.probe(validated.executable)
        except (CoreError, OSError, subprocess.TimeoutExpired):
            runtime = None
    if runtime is None:
        candidates = java.discover()
        try:
            runtime = select_java_runtime(candidates, None if settings['javaVersion'] == 'auto' else int(settings['javaVersion']))
        except CoreError:
            runtime = None
    cancellation.check()
    with store.lock:
        found = runtime is not None
        if store.settings['javaPath'] != configured:
            found = bool(store.settings['javaPath'])
        elif runtime is not None:
            store.persist(settings={**store.settings, 'javaPath': str(runtime.executable)})
            store.publish()
    result = FirstRunSetup(found)
    app.get('events', EventManager).publish(CoreEvent('first_run', result))
    return result
