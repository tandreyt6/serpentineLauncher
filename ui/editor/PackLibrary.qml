import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher

UG.Page {
    id: page
    tag: "editor.content.library.page"
    required property string buildId
    required property string workspaceKey
    property string contentKind: "resourcepack"
    function handleShortcut(action) {
        if (action === "refresh") {
            Session.command("editor_scan", buildId)
            return true
        }
        return false
    }
    readonly property string directory: contentKind === "shader" ? "shaderpacks" : "resourcepacks"
    readonly property var browser: Session.modBrowser(buildId, contentKind)
    readonly property var buildData: { Session.builds; return Session.build(buildId) }
    readonly property bool protectedBuild: false
    readonly property var installed: {
        Session.editorRevision
        return Session.editorEntries(buildId).filter(entry => entry.path.toLowerCase().startsWith(page.directory + "/") && !entry.path.slice(page.directory.length + 1).includes("/") && (entry.folder || /\.zip(\.disabled)?$/i.test(entry.name)))
    }
    signal deleteRequested(string path)
    signal importRequested(string directory)
    Component.onCompleted: scanTimer.restart()
    onContentKindChanged: scanTimer.restart()
    onVisibleChanged: if (visible) scanTimer.restart()
    Timer {
        id: scanTimer
        interval: 0
        onTriggered: if (page.visible) Session.command("editor_scan", page.buildId)
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Style.value(page.appearance, "packLibraryMargins")
        spacing: Style.value(page.appearance, "packLibrarySpacing")
        RowLayout {
            Layout.fillWidth: true
            UG.Button {
                tag: "editor.content.library.refresh"
                textKey: "common.refresh"
                onClicked: Session.command("editor_scan", page.buildId)
            }
            UG.Button {
                tag: "editor.content.library.import"
                textKey: "editor.add"
                iconSource: IconSources.add || ""
                enabled: !page.protectedBuild
                onClicked: page.importRequested(page.directory)
            }
            OpenFolderButton {
                tag: "editor.content.library.folder"
                objectName: "editor." + page.contentKind + ".folder"
                buildId: page.buildId
                directory: page.directory
                textKey: page.contentKind === "shader" ? "editor.open_shaders_folder" : "editor.open_resourcepacks_folder"
            }
            Item { Layout.fillWidth: true }
            UG.Button {
                tag: "editor.content.library.catalog"
                objectName: "content.catalog.open." + page.contentKind
                textKey: page.contentKind === "shader" ? "editor.shader_catalog" : "editor.resourcepack_catalog"
                iconSource: IconSources.add || ""
                onClicked: Editors.openContentCatalog(page.buildId, page.contentKind, page.workspaceKey)
            }
            UG.Button {
                tag: "editor.content.library.sync"
                textKey: "editor.sync"
                enabled: page.browser.queueModel.count > 0 && !page.browser.queueModel.syncing && !page.protectedBuild
                onClicked: page.browser.synchronize()
            }
        }
        UG.ScrollArea {
            tag: "editor.content.library.scroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            ColumnLayout {
                width: parent.width
                spacing: Style.value(page.appearance, "packLibrarySpacing2")
                Repeater {
                    model: page.browser.queueModel
                    delegate: ContentQueueRow {
                        required property var modelData
                        Layout.fillWidth: true
                        entryData: modelData.detail
                        protectedBuild: page.protectedBuild
                        onRemoveRequested: key => page.browser.remove(key)
                    }
                }
                Repeater {
                    model: page.installed
                    delegate: UG.Frame {
                        tag: "editor.content.library.entry"
                        required property var modelData
                        objectName: "content.installed." + modelData.path
                        Layout.fillWidth: true
                        implicitHeight: Style.value(page.appearance, "packLibraryImplicitHeight")
                        padding: Style.value(page.appearance, "packLibraryPadding")
                        RowLayout {
                            anchors.fill: parent
                            spacing: Style.value(page.appearance, "packLibrarySpacing3")
                            UG.Icon { tag: "editor.content.library.icon"; source: IconSources[page.contentKind === "shader" ? "shaders" : "resource-packs"] || "" }
                            UG.UiText { tag: "editor.content.library.title"; Layout.fillWidth: true; displayText: modelData.name; elide: Text.ElideRight }
                            UG.Button {
                                tag: "editor.content.library.delete"
                                iconSource: IconSources.delete || ""
                                displayText: ""
                                useDisplayText: true
                                implicitWidth: Style.value(page.appearance, "packLibraryImplicitWidth")
                                enabled: !page.protectedBuild
                                Accessible.name: Session.text("common.delete")
                                onClicked: page.deleteRequested(modelData.path)
                            }
                        }
                    }
                }
                UG.UiText { tag: "editor.content.library.empty"; Layout.fillWidth: true; visible: !page.installed.length; textKey: "editor.content_empty" }
            }
        }
    }
}
