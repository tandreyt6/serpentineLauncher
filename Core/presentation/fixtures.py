from Core.configuration.settings import APPLICATION_SETTINGS, DEFAULT_JAVA_MEMORY_PERCENT, PREVIEW_MEMORY_LIMIT_MB
from Core.presentation.contracts import AccountPreview, BuildPreview, CorePreview, QueuedModPreview


BUILDS = (
    BuildPreview("quiet_valley", "Quiet Valley", "1.21.1", "Fabric", "0.16.10", "demo.valley", 0),
    BuildPreview("create_workshop", "Create Workshop", "1.20.1", "Forge", "47.3.0", "demo.workshop", 1, True),
    BuildPreview("vanilla_days", "Vanilla Days", "1.21.4", "Vanilla", "", "demo.vanilla", 2),
    BuildPreview("beyond_the_pines", "Beyond the Pines", "1.21.1", "NeoForge", "21.1.115", "demo.pines", 3),
)
ACCOUNTS = (AccountPreview("alex", "Alex", "AX"), AccountPreview("builder", "Builder", "BR"))
MOD_CATALOG = (
    QueuedModPreview("sodium", "Sodium", "https://modrinth.com/mod/sodium", ""),
    QueuedModPreview("lithium", "Lithium", "https://modrinth.com/mod/lithium", ""),
    QueuedModPreview("fabric-api", "Fabric API", "https://modrinth.com/mod/fabric-api", ""),
    QueuedModPreview("create", "Create", "https://modrinth.com/mod/create", ""),
    QueuedModPreview("jei", "JEI", "https://modrinth.com/mod/jei", ""),
)
CORES = (
    CorePreview("fabric_1.21.1_0.16.10", "1.21.1", "Fabric", "0.16.10", True),
    CorePreview("forge_1.20.1_47.3.0", "1.20.1", "Forge", "47.3.0", True),
    CorePreview("vanilla_1.21.4", "1.21.4", "Vanilla", "", True),
    CorePreview("neoforge_1.21.1_21.1.115", "1.21.1", "NeoForge", "21.1.115", False, 63),
    CorePreview("quilt_1.21.1_0.27.1", "1.21.1", "Quilt", "0.27.1", False),
)
SETTINGS = {
    **APPLICATION_SETTINGS,
    "panelSide": "left",
    "panelMode": "hover",
    "panelLayout": "overlay",
    "panelAlign": "center",
    "buildView": "cards",
    "buildCardSize": "small",
    "coreView": "cards",
    "safeMode": True,
    "javaPath": "",
    "javaVersion": "auto",
    "memoryMin": "512",
    "memoryMax": str(PREVIEW_MEMORY_LIMIT_MB * DEFAULT_JAVA_MEMORY_PERCENT // 100),
    "jvmArgs": "",
    "javaRestrictions": "default",
    "closeAction": "tray",
    "launchAction": "nothing",
    "finishAction": "last",
    "modDrop": True,
    "logMode": "normal",
    "zipBatch": "5",
    "reducedMotion": False,
}
