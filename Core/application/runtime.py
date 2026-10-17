from Core.network.downloads import DownloadManager
from Core.installation.forge_installation import ForgeInstallerManager
from Core.installation.installation import InstallationManager, MetadataManager
from Core.game.java import JavaManager
from Core.game.launch import LaunchManager
from Core.content.mods.mods import ModMetadataManager
from Core.content.mrpacks import MrpackMetadataManager
from Core.network.network import NetworkManager
from Core.game.processes import ProcessAdapter, default_process_adapter
from Core.game.process_manager import ProcessDriver
from Core.application.router import AccessManager, AppManager, EventManager
from Core.application.settings import CoreConfig
from Core.application.storage import FileManager
from Core.application.tasks import TaskManager
from Core.appearance.appearance_packs import AppearanceFileDriver
from Core.application.application import ApplicationManager
from Core.application.application_store import ApplicationStore
from Core.content.catalogue import CatalogueManager
from Core.content.editor_files import EditorFilesManager
from Core.content.providers.modrinth import ModrinthManager
from Core.content.mods.mod_queue import ModQueueManager
from Core.content.mods.mod_imports import ModImportManager
from Core.content.mods.mod_inventory import ModInventoryManager
from Core.application.log_storage import LogFileDriver
from Core.application.logging_manager import LogManager
from Core.updates.releases import UpdateManager


class CoreRuntime:
    def __init__(self, config: CoreConfig, process_adapter: ProcessAdapter | None = None) -> None:
        self.app = AppManager()
        self.app.register("config", config)
        self.app.register("events", EventManager())
        self.app.register("access", AccessManager(config.control_wait_interval))
        self.app.register("files", FileManager(config))
        self.app.register("log_files", LogFileDriver())
        self.app.register("logs", LogManager(self.app, config))
        self.app.register("network", NetworkManager(config))
        self.app.register("updates", UpdateManager(self.app, config))
        self.app.register("tasks", TaskManager(self.app, config.task_workers))
        self.app.register("downloads", DownloadManager(self.app, config))
        self.app.register("metadata", MetadataManager(self.app, config))
        self.app.register("mods", ModMetadataManager(self.app, config))
        self.app.register("mrpacks", MrpackMetadataManager(self.app, config))
        self.app.register("installation", InstallationManager(self.app, config))
        self.app.register("processes", ProcessDriver(process_adapter or default_process_adapter()))
        self.app.register("java", JavaManager(self.app, config))
        self.app.register("forge_installers", ForgeInstallerManager(self.app, config))
        self.app.register("launch", LaunchManager(self.app, config))
        self.app.register("application_store", ApplicationStore(self.app, config))
        self.app.register("catalogue", CatalogueManager(self.app, config))
        self.app.register("editor_files", EditorFilesManager(self.app, config))
        self.app.register("modrinth", ModrinthManager(self.app, config))
        self.app.register("mod_inventory", ModInventoryManager(self.app, config))
        self.app.register("mod_queue", ModQueueManager(self.app, config))
        self.app.register("mod_imports", ModImportManager(self.app, config))
        self.app.register("appearance_files", AppearanceFileDriver(config))
        self.app.register("application", ApplicationManager(self.app, config))
        self._closed = False

    def close(self, force: bool = False) -> None:
        if self._closed:
            return
        launch = self.app.get("launch", LaunchManager)
        if launch.has_active_clients() and not force:
            launch.close()
        self.app.get("tasks", TaskManager).close()
        self.app.get("application", ApplicationManager).close()
        self.app.get("catalogue", CatalogueManager).close()
        self.app.get("installation", InstallationManager).close()
        self.app.get("mods", ModMetadataManager).close()
        self.app.get("mod_queue", ModQueueManager).close()
        self.app.get("mod_imports", ModImportManager).close()
        self.app.get("mrpacks", MrpackMetadataManager).close()
        launch.close(force)
        self.app.get("downloads", DownloadManager).close()
        self.app.get("access", AccessManager).close()
        self.app.get("network", NetworkManager).close()
        self.app.get("files", FileManager).close()
        self.app.get("events", EventManager).close()
        self._closed = True
