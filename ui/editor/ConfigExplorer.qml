import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

Item {
    id: explorer
    property string buildId: ""
    property string rootDirectory: ""
    property string directory: rootDirectory
    property bool configOnly: true
    property bool editable: true
    property string folderTextKey: "cores.open_folder"
    property bool searching: false
    function handleShortcut(action) {
        if (action === "find") {
            searching = true
            fileSearch.forceActiveFocus()
            fileSearch.selectAll()
        } else if (action === "refresh")
            Session.command("editor_scan", buildId)
        else if (action === "back" && directory !== rootDirectory)
            directory = directory.split("/").slice(0, -1).join("/")
        else
            return false
        return true
    }
    readonly property var entries: {
        Session.editorRevision
        const all = Session.live ? Session.editorEntries(buildId) : Editors.configs(directory)
        const prefix = directory.length ? directory + "/" : ""
        return all.filter(entry => !Session.live || entry.path.startsWith(prefix) && !entry.path.slice(prefix.length).includes("/")).filter(entry => !configOnly || (entry.folder ? !Session.live || all.some(child => child.path.startsWith(entry.path + "/") && !child.folder && child.config) : !Session.live || entry.config)).filter(entry => !searching || entry.name.toLowerCase().includes(fileSearch.text.toLowerCase())).map(entry => ({
                    key: entry.path,
                    path: entry.path,
                    name: entry.name,
                    kind: entry.folder ? "directory" : "file",
                    icon: IconSources[entry.folder ? "folder" : configOnly ? "config" : "file"] || "",
                    enabled: true
                }))
    }
    onRootDirectoryChanged: directory = rootDirectory
    signal importRequested
    signal deleteRequested(string path)
    signal fileOpened(string path)
    ColumnLayout {
        anchors.fill: parent
        spacing: Style.value((explorer.Window.window ? explorer.Window.window.appearance : null), "configExplorerSpacing")
        RowLayout {
            Layout.fillWidth: true
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value((explorer.Window.window ? explorer.Window.window.appearance : null), "configExplorerImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                tag: "ui.files.back"
                stateKey: "secondary"
                textKey: "common.back"
                iconSource: IconSources["back"] || ""
                enabled: explorer.directory !== explorer.rootDirectory
                onActivated: explorer.directory = explorer.directory.split("/").slice(0, -1).join("/")
            }
            UG.UiText {
                tag: "ui.files.path"
                Layout.fillWidth: true
                displayText: "/" + explorer.directory
                wrapMode: Text.NoWrap
                elide: Text.ElideLeft
            }
            UG.Button {
                id: button1
                implicitWidth: Math.max(Style.value((explorer.Window.window ? explorer.Window.window.appearance : null), "configExplorerImplicitWidth"), metrics1.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics1
                    text: button1.text
                    font.family: button1.appearance.fontFamily
                    font.pixelSize: button1.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                tag: "ui.files.refresh"
                objectName: "editor.files.refresh"
                stateKey: "secondary"
                textKey: "common.refresh"
                iconSource: IconSources["refresh"] || ""
                onActivated: Session.command("editor_scan", explorer.buildId)
            }
            UG.Button {
                id: button2
                implicitWidth: Math.max(Style.value((explorer.Window.window ? explorer.Window.window.appearance : null), "configExplorerImplicitWidth"), metrics2.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics2
                    text: button2.text
                    font.family: button2.appearance.fontFamily
                    font.pixelSize: button2.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                tag: "ui.files.import"
                stateKey: "secondary"
                textKey: "common.add"
                iconSource: IconSources["add"] || ""
                visible: !explorer.configOnly
                enabled: explorer.editable
                onActivated: explorer.importRequested()
            }
            OpenFolderButton {
                tag: "ui.files.folder"
                objectName: "editor.files.folder"
                buildId: explorer.buildId
                directory: explorer.rootDirectory.length ? explorer.rootDirectory : explorer.directory
                textKey: explorer.folderTextKey
            }
        }
        UG.TextField {
            id: fileSearch
            tag: "ui.files.search"
            objectName: "editor.files.search"
            visible: explorer.searching
            Layout.fillWidth: true
            textKey: "common.search"
            iconSource: IconSources["search"]
            Keys.onEscapePressed: event => { explorer.searching = false; event.accepted = true }
        }
        UG.FileSystem {
            tag: "ui.files.explorer"
            objectName: "editor.files"
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: explorer.entries
            path: explorer.directory
            navigationVisible: false
            pathVisible: false
            actions: explorer.configOnly ? [
                {
                    key: "open",
                    text_key: "files.open"
                }
            ] : [
                {
                    key: "open",
                    text_key: "files.open"
                },
                {
                    key: "delete",
                    text_key: "common.delete",
                    enabled: explorer.editable
                }
            ]
            onActionRequested: (action, keys, path, value) => {
                if (action === "navigate") {
                    if (!explorer.rootDirectory.length || path === explorer.rootDirectory || path.startsWith(explorer.rootDirectory + "/"))
                        explorer.directory = path
                } else if (action === "open" && keys.length) {
                    const entry = explorer.entries.find(entry => entry.key === keys[0])
                    if (entry && entry.kind === "directory")
                        explorer.directory = entry.path
                    else
                        explorer.fileOpened(keys[0])
                } else if (action === "delete" && explorer.editable)
                    keys.forEach(key => explorer.deleteRequested(key))
                else if (action === "refresh")
                    Session.command("editor_scan", explorer.buildId)
                else if (action === "back" && explorer.directory !== explorer.rootDirectory)
                    explorer.directory = explorer.directory.split("/").slice(0, -1).join("/")
            }
        }
    }
}
