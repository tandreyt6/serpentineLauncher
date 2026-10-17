from pathlib import PurePosixPath

from Core.presentation.contracts import ConfigPreview, LogPreview


CONFIG_EXTENSIONS = frozenset((".json", ".toml", ".yaml", ".yml", ".properties", ".cfg", ".ini", ".conf", ".txt", ".xml"))
CONFIGS = (
    ConfigPreview("options.txt", "renderDistance:12\nmaxFps:120\nfullscreen:false\n"),
    ConfigPreview("config/example.json", '{\n  "enabled": true,\n  "quality": 3,\n  "worldName": "My world"\n}\n'),
    ConfigPreview("config/example.toml", "[graphics]\nshadows = true\nquality = 3\n"),
    ConfigPreview("config/client/video.yaml", "shadows: true\nquality: 3\n"),
    ConfigPreview("config/client/preferences.properties", "ui.scale=2\nui.animations=true\n"),
)
LOGS = (
    LogPreview("2026-10-04", "latest.log", '<log4j:Event logger="Sodium" timestamp="1791886838479" level="INFO" thread="main">\n  <log4j:Message><![CDATA[Loaded configuration file for Sodium: 45 options available, 1 override(s) found]]></log4j:Message>\n</log4j:Event>\n<log4j:Event logger="FabricLoader/Mixin" timestamp="1791886838491" level="WARN" thread="main">\n  <log4j:Message><![CDATA[Error loading class: example.OptionalIntegration (java.lang.ClassNotFoundException: example.OptionalIntegration)]]></log4j:Message>\n</log4j:Event>\n<log4j:Event logger="Minecraft" timestamp="1791886838588" level="ERROR" thread="Render thread">\n  <log4j:Message><![CDATA[Unable to load an optional resource]]></log4j:Message>\n  <log4j:Throwable><![CDATA[java.io.IOException: Resource is unavailable\n\tat example.ResourceLoader.load(ResourceLoader.java:42)\nCaused by: java.io.FileNotFoundException: optional-resource.json]]></log4j:Throwable>\n</log4j:Event>\n'),
    LogPreview("2026-10-04", "2026-10-04-1.log", "[09:08:11] [main/INFO] Loading Minecraft\n[09:10:27] [Server thread/INFO] Saving world\n[09:10:28] [main/INFO] Stopping\n"),
    LogPreview("2026-10-03", "2026-10-03-2.log", "[20:12:08] [main/INFO] Loading Minecraft\n[20:32:41] [main/INFO] Stopping\n"),
    LogPreview("2026-10-03", "2026-10-03-1.log", "[16:03:10] [main/INFO] Loading Minecraft\n[17:19:22] [main/INFO] Stopping\n"),
    LogPreview("2026-10-02", "2026-10-02-1.log", "[18:41:03] [main/INFO] Loading Minecraft\n[19:02:18] [main/INFO] Stopping\n"),
)


def config_entries(directory: str) -> list[dict]:
    prefix = directory.rstrip("/") + "/" if directory else ""
    folders: set[str] = set()
    files = []
    for entry in CONFIGS:
        if PurePosixPath(entry.path).suffix.lower() not in CONFIG_EXTENSIONS or not entry.path.startswith(prefix):
            continue
        remaining = entry.path[len(prefix):]
        if "/" in remaining:
            folders.add(remaining.split("/")[0])
        else:
            files.append({"name": remaining, "path": entry.path, "folder": False})
    return [{"name": folder, "path": prefix + folder, "folder": True} for folder in sorted(folders)] + files
