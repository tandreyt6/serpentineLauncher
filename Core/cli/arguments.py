from argparse import ArgumentParser

from Core.configuration.settings import APP_NAME, APP_VERSION
from Core.cli.contracts import CliRequest


def parse_arguments(arguments: list[str]) -> CliRequest:
    parser = ArgumentParser(description=APP_NAME + " " + APP_VERSION)
    parser.add_argument("--version", action="version", version=APP_VERSION)
    parser.add_argument("--format", choices=("text", "json"), default="text", help="CLI output format; always English")
    parser.add_argument("--theme-preview", action="store_true", help="Open an isolated UI preview")
    commands = parser.add_subparsers(dest="action")
    for action in ("builds", "accounts", "cores", "clients", "tasks"):
        commands.add_parser(action, help="List " + action)
    launch = commands.add_parser("launch", help="Launch a build; start in the background if needed")
    launch.add_argument("id")
    launch.add_argument("--account", default="", help="Account ID or player name")
    for action in ("close", "kill"):
        command = commands.add_parser(action, help="Request client shutdown" if action == "close" else "Force client shutdown")
        command.add_argument("id")
        if action == "kill":
            command.add_argument("--confirm", action="store_true", required=True, help="Confirm forced termination")
    install = commands.add_parser("install", help="Install a Minecraft core")
    install.add_argument("minecraft")
    install.add_argument("--loader", choices=("Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"), default="Vanilla")
    install.add_argument("--loader-version", default="")
    create = commands.add_parser("create", help="Create a build and install its core")
    create.add_argument("id")
    create.add_argument("--title", required=True)
    create.add_argument("--minecraft", required=True)
    create.add_argument("--loader", choices=("Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"), default="Vanilla")
    create.add_argument("--loader-version", default="")
    account = commands.add_parser("add-account", help="Add an offline account")
    account.add_argument("name")
    settings = commands.add_parser("settings", help="Read or change a setting")
    settings.add_argument("key", nargs="?", default="")
    settings.add_argument("value", nargs="?", default=None)
    for action in ("pause", "resume", "cancel"):
        command = commands.add_parser(action, help=action.capitalize() + " a task")
        command.add_argument("id")
    normalized = []
    format_args = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument.startswith("--format="):
            format_args.append(argument)
        elif argument == "--format" and index + 1 < len(arguments):
            format_args.extend(arguments[index:index + 2])
            index += 1
        else:
            normalized.append(argument)
        index += 1
    values = vars(parser.parse_args(format_args + normalized))
    action = values.pop("action") or "activate"
    format = values.pop("format")
    preview = values.pop("theme_preview")
    key = values.pop("id", values.get("key", ""))
    value = values.pop("account", values.get("name", ""))
    if action == "settings":
        key = values.pop("key")
        value = values.pop("value")
        action = "setting" if value is not None else "settings"
        value = value or ""
    return CliRequest(action, key, value, tuple((name, str(value)) for name, value in values.items()), format, preview)
