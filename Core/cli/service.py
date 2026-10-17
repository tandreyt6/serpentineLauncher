from Core.application.diagnostics import diagnostic
import json

from dataclasses import asdict, is_dataclass
from threading import Event

from Core.cli.contracts import CliRequest, CliResponse
from Core.application.application import ApplicationManager
from Core.application.application_contracts import ApplicationCommand, BackendResult
from Core.application.application_store import ApplicationStore
from Core.content.catalogue import CatalogueManager
from Core.application.contracts import CoreError, CoreEvent, InstallRequest
from Core.installation.installation import core_identifier
from Core.game.launch import LaunchManager
from Core.application.logging_manager import LogManager
from Core.application.router import AppManager, EventManager
from Core.application.tasks import TaskManager


def json_value(value: object) -> object:
    if is_dataclass(value):
        return {key: json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    return value


class CliService:
    def __init__(self, app: AppManager, activation: Event) -> None:
        self._app = app
        self._activation = activation

    def execute(self, command: ApplicationCommand, nested: bool = False) -> object:
        task = self._app.get("application", ApplicationManager).submit(command)
        tasks = self._app.get("tasks", TaskManager)
        try:
            result = tasks.wait(task)
        finally:
            tasks.release(task)
        return tasks.wait(result) if nested and isinstance(result, str) else result

    def handle(self, request: CliRequest) -> CliResponse:
        try:
            self._app.get("logs", LogManager).write("CLI " + request.action + " " + request.key)
            result = self.run(request)
            if request.format == "json":
                output = json.dumps({"ok": True, "result": json_value(result)}, ensure_ascii=False)
            elif isinstance(result, str):
                output = result
            else:
                output = json.dumps(json_value(result), ensure_ascii=False, indent=2)
            return CliResponse(0, output + "\n" if output else "")
        except Exception as error:
            self._app.get("logs", LogManager).write("CLI failed: " + str(error), "ERROR")
            if request.format == "json":
                return CliResponse(1, json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False) + "\n")
            return CliResponse(1, "", "Error: " + str(error) + "\n")

    def run(self, request: CliRequest) -> object:
        action, key, value = request.action, request.key, request.value
        store = self._app.get("application_store", ApplicationStore)
        snapshot = store.snapshot()
        if action == "activate":
            self._activation.set()
            self._app.get("events", EventManager).publish(CoreEvent("backend", BackendResult("activate")))
            return "Launcher activated"
        if action in ("builds", "accounts", "cores"):
            return getattr(snapshot, action)
        if action == "clients":
            return self._app.get("launch", LaunchManager).snapshots()
        if action == "tasks":
            return self._app.get("tasks", TaskManager).snapshots()
        if action == "settings":
            settings = dict(snapshot.settings)
            if key and key not in settings:
                raise CoreError(diagnostic('service.unknown.setting'))
            return settings[key] if key else settings
        if action in ("pause", "resume", "cancel"):
            return getattr(self._app.get("tasks", TaskManager), action)(key)
        if action == "install":
            fields = dict(request.fields)
            minecraft, loader, version = fields["minecraft"], fields["loader"], fields["loader_version"]
            if loader != "Vanilla" and not version:
                raise CoreError(diagnostic('service.a.loader.version.is.required'))
            self._app.get("tasks", TaskManager).wait(self._app.get("catalogue", CatalogueManager).initialize())
            self.execute(ApplicationCommand("catalogue", loader, minecraft))
            identifier = core_identifier(InstallRequest(minecraft, loader, version))
            return self.execute(ApplicationCommand("download", identifier), nested=True)
        if action == "launch":
            account = next((account.id for account in snapshot.accounts if account.id == value or account.name.casefold() == value.casefold()), value)
            return self.execute(ApplicationCommand("play", key, account), nested=True)
        if action in ("close", "kill"):
            if action == "kill" and dict(request.fields).get("confirm") != "True":
                raise CoreError(diagnostic('service.forced.termination.requires.confirm'))
            return self.execute(ApplicationCommand("kill_client" if action == "kill" else "close_client", key), nested=True)
        if action == "add-account":
            return self.execute(ApplicationCommand("add_account", value=request.value))
        if action in ("create", "setting"):
            return self.execute(ApplicationCommand(action, key, value, request.fields))
        raise CoreError(diagnostic('service.unknown.cli.command'))
