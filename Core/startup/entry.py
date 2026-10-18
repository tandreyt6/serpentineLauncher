from __future__ import annotations

import sys

from threading import Event, Thread
from time import sleep

from Core.configuration.settings import IPC_POLL_INTERVAL_SECONDS
from Core.cli.contracts import CliRequest, CliResponse
from Core.cli.instance import InstanceDriver


def emit_response(response: CliResponse) -> None:
    for stream, text in ((sys.stdout, response.stdout), (sys.stderr, response.stderr)):
        if stream is not None and text:
            stream.write(text)
            stream.flush()


def run_gui(core: CoreRuntime, instance: InstanceDriver, preview: bool, activation: Event) -> int:
    from Core.presentation.runtime.entrypoint import main as start_gui
    return start_gui(core, instance, preview, activation)


class InitialCommand:
    def __init__(self, service: CliService, request: CliRequest) -> None:
        self._service = service
        self._request = request
        self.ready = Event()
        self.response = None
        self.thread = Thread(target=self._run, name="launcher-cli-command", daemon=True)

    def _run(self) -> None:
        self.response = self._service.handle(self._request)
        try:
            emit_response(self.response)
        finally:
            self.ready.set()


def main(request: CliRequest, instance: InstanceDriver) -> int:
    if request.action == "activate":
        return run_gui(None, instance, request.preview, Event())
    from Core.cli.service import CliService
    from Core.application.application import ApplicationManager
    from Core.application.application_contracts import ApplicationCommand
    from Core.application.bootstrap import create_core_runtime
    from Core.game.launch import LaunchManager
    from Core.application.router import EventManager
    from Core.application.tasks import TaskManager
    core = create_core_runtime()
    activation = Event()
    try:
        task = core.app.get("application", ApplicationManager).submit(ApplicationCommand("bootstrap"))
        core.app.get("tasks", TaskManager).wait(task)
        service = CliService(core.app, activation)
        instance.start(service.handle)
        if request.action not in ("launch", "create", "install"):
            response = service.handle(request)
            emit_response(response)
            if activation.is_set():
                return run_gui(core, instance, False, activation)
            return response.code
        initial = InitialCommand(service, request)
        initial.thread.start()
        while True:
            core.app.get("events", EventManager).drain()
            if activation.is_set():
                return run_gui(core, instance, False, activation)
            if not initial.ready.is_set():
                sleep(IPC_POLL_INTERVAL_SECONDS)
                continue
            if initial.response.code:
                return initial.response.code
            if request.action == "launch":
                from Core.presentation.runtime.background import main as start_background
                return start_background(core, activation)
            active = core.app.get("launch", LaunchManager).has_active_clients()
            busy = any(task.state in ("queued", "running", "paused", "cancelling") for task in core.app.get("tasks", TaskManager).snapshots())
            if not active and not busy:
                return 0
            sleep(IPC_POLL_INTERVAL_SECONDS)
    finally:
        instance.close()
        core.close()


