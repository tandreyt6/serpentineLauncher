import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher

UG.Frame {
    id: row
    tag: "editor.content.queue.entry"
    required property var entryData
    property bool protectedBuild: false
    signal removeRequested(string key)
    readonly property bool downloading: entryData.state === "downloading"
    objectName: "mod.queued." + entryData.owner_id + "." + (entryData.queue_id || entryData.id)
    padding: Style.value(row.appearance, "contentQueueRowPadding")
    implicitHeight: entryData.required_by && entryData.required_by.length ? Style.value(row.appearance, "contentQueueRowImplicitHeight") : Style.value(row.appearance, "contentQueueRowImplicitHeight2")
    RowLayout {
        anchors.fill: parent
        spacing: Style.value(row.appearance, "contentQueueRowSpacing")
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Style.value(row.appearance, "contentQueueRowSpacing2")
            UG.UiText {
                tag: "editor.content.queue.title"
                Layout.fillWidth: true
                displayText: row.entryData.title + (row.entryData.version_number ? " · " + row.entryData.version_number : "")
                elide: Text.ElideRight
            }
            UG.UiText {
                tag: "editor.content.queue.dependency"
                Layout.fillWidth: true
                visible: !!row.entryData.required_by && row.entryData.required_by.length > 0
                displayText: Session.text("editor.mod_dependency_for") + ": " + (row.entryData.required_by || []).join(", ")
                elide: Text.ElideRight
            }
            RowLayout {
                Layout.fillWidth: true
                UG.UiText {
                    tag: "editor.content.queue.state"
                    Layout.fillWidth: true
                    displayText: row.downloading ? row.entryData.verified ? Session.text("editor.download_verified") : Session.text("common.loading") : Session.text("editor.mod_queued")
                    elide: Text.ElideRight
                }
                UG.UiText {
                    tag: "editor.content.queue.percent"
                    visible: row.downloading
                    displayText: { Session.revision; return row.entryData.total_bytes === null || row.entryData.total_bytes === undefined ? Session.formatDownloadBytes(row.entryData.completed_bytes || 0) : Session.formatText("common.percent", {value: Math.floor((row.entryData.progress || 0) * 100)}) }
                }
            }
            UG.ProgressBar {
                tag: "editor.content.queue.progress"
                objectName: "content.progress." + (row.entryData.queue_id || row.entryData.id)
                Layout.fillWidth: true
                opacity: row.downloading ? 1 : 0
                indeterminate: row.downloading && (row.entryData.total_bytes === null || row.entryData.total_bytes === undefined) && !row.entryData.verified
                value: row.entryData.progress || 0
                smooth: !Session.settings.reducedMotion
            }
        }
        UG.Button {
            tag: "editor.content.queue.remove"
            objectName: "mod.remove." + (row.entryData.queue_id || row.entryData.id)
            displayText: ""
            useDisplayText: true
            iconSource: IconSources.close || ""
            implicitWidth: Style.value(row.appearance, "contentQueueRowImplicitWidth")
            enabled: !row.downloading && !row.protectedBuild
            Accessible.name: Session.text("editor.remove_queued")
            onClicked: row.removeRequested(row.entryData.queue_id || row.entryData.id)
        }
    }
}
