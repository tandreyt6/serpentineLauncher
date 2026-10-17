import "../Launcher/Style.js" as Style
import QtQuick
import Working.Gui as UG
import QtQuick.Layouts
import QtQuick.Controls as QC
import Launcher

UG.PopupPanel {
    id: activity
    height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, Style.value(activity.appearance, "activityPopupHeight"), parent ? parent.height : Style.value(activity.appearance, "activityPopupHeight"))
    tag: "ui.pages.activitypopup.1"
    objectName: "tasks.popup"
    width: activity.appearance.tasksWidth
    padding: Style.value(activity.appearance, "activityPopupPadding")
    focus: true
    property Item dialogHost: QC.Overlay.overlay
    property string clientId: ""
    readonly property var clients: Session.builds.filter(build => build.running)
    transformOrigin: Item.BottomRight
    onOpened: downloadsView.forceLayout()
    background: UG.Frame {
        tag: "ui.pages.activitypopup.2"
        padding: 0
        displayText: ""
        useDisplayText: true
    }
    contentItem: Item {
        width: activity.availableWidth
        height: activity.availableHeight
        implicitHeight: activityHeader.implicitHeight + activity.appearance.spacing + Math.max(downloadsView.contentHeight, Session.downloads.length ? 2 * Style.value(activity.appearance, "activityPopupPreferredHeight") : 0)
        ColumnLayout {
            id: activityHeader
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            spacing: Style.value(activity.appearance, "activityPopupSpacing")
            RowLayout {
                width: activityHeader.width
                UG.UiText {
                    tag: "ui.pages.activitypopup.3"
                    verticalAlignment: Text.AlignVCenter
                    textKey: "activity.clients"
                    typographyRole: (true) ? "caption" : "body"
                    font.pixelSize: Style.value(activity.appearance, "activityPopupPixelSize")
                }
                Item {
                    Layout.fillWidth: true
                }
                UG.Button {
                    id: button0
                    implicitWidth: Math.max(Style.value(activity.appearance, "activityPopupImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                    TextMetrics {
                        id: metrics0
                        text: button0.text
                        font.family: button0.appearance.fontFamily
                        font.pixelSize: button0.appearance.fontSize
                        font.weight: Font.DemiBold
                    }

                    tag: "ui.pages.activitypopup.4"
                    stateKey: (false) ? "primary" : "secondary"
                    displayText: ""
                    useDisplayText: true
                    iconSource: IconSources["close"] || ""
                    Accessible.name: Session.text("common.close")
                    width: Style.value(activity.appearance, "activityPopupWidth")
                    height: Style.value(activity.appearance, "activityPopupHeight2")
                    onClicked: activity.close()
                }
            }
            Repeater {
                model: activity.clients
                delegate: RowLayout {
                    width: activityHeader.width
                    required property var modelData
                    objectName: "tasks.client." + modelData.id
                    Layout.fillWidth: true
                    spacing: Style.value(activity.appearance, "activityPopupSpacing2")
                    UG.UiText {
                        tag: "ui.pages.activitypopup.5"
                        verticalAlignment: Text.AlignVCenter
                        Layout.fillWidth: true
                        displayText: modelData.title
                        elide: Text.ElideRight
                        wrapMode: Text.NoWrap
                        font.pixelSize: Style.value(activity.appearance, "activityPopupPixelSize2")
                    }
                    UG.Button {
                        id: button1
                        implicitWidth: Math.max(Style.value(activity.appearance, "activityPopupImplicitWidth"), metrics1.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                        TextMetrics {
                            id: metrics1
                            text: button1.text
                            font.family: button1.appearance.fontFamily
                            font.pixelSize: button1.appearance.fontSize
                            font.weight: Font.DemiBold
                        }

                        tag: "ui.pages.activitypopup.6"
                        stateKey: (false) ? "primary" : "secondary"
                        iconSource: IconSources[{
                                "common.save": "save",
                                "common.back": "back",
                                "common.close": "close",
                                "common.cards": "view-grid",
                                "common.list": "view-list",
                                "builds.new": "add",
                                "builds.edit": "edit",
                                "builds.delete": "delete",
                                "builds.about": "info",
                                "profile.add": "add",
                                "editor.add_mod": "add",
                                "common.edit": "edit",
                                "common.delete": "delete",
                                "common.refresh": "refresh",
                                "common.add": "add"
                            }["common.close"] || ""] || ""
                        textKey: "common.close"
                        Layout.preferredHeight: Style.value(activity.appearance, "activityPopupPreferredHeight")
                        Layout.maximumHeight: Style.value(activity.appearance, "activityPopupMaximumHeight")
                        onClicked: Session.command("close_client", modelData.id)
                    }
                    UG.Button {
                        id: button2
                        implicitWidth: Math.max(Style.value(activity.appearance, "activityPopupImplicitWidth"), metrics2.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                        TextMetrics {
                            id: metrics2
                            text: button2.text
                            font.family: button2.appearance.fontFamily
                            font.pixelSize: button2.appearance.fontSize
                            font.weight: Font.DemiBold
                        }

                        tag: "ui.pages.activitypopup.7"
                        objectName: "tasks.kill." + modelData.id
                        stateKey: (false) ? "primary" : "secondary"
                        iconSource: IconSources[{
                                "common.save": "save",
                                "common.back": "back",
                                "common.close": "close",
                                "common.cards": "view-grid",
                                "common.list": "view-list",
                                "builds.new": "add",
                                "builds.edit": "edit",
                                "builds.delete": "delete",
                                "builds.about": "info",
                                "profile.add": "add",
                                "editor.add_mod": "add",
                                "common.edit": "edit",
                                "common.delete": "delete",
                                "common.refresh": "refresh",
                                "common.add": "add"
                            }["activity.kill"] || ""] || ""
                        textKey: "activity.kill"
                        Layout.preferredHeight: Style.value(activity.appearance, "activityPopupPreferredHeight")
                        Layout.maximumHeight: Style.value(activity.appearance, "activityPopupMaximumHeight")
                        onClicked: {
                            activity.clientId = modelData.id
                            killDialog.detail = modelData.title
                            killDialog.focusReturnItem = button2
                            killDialog.open()
                        }
                    }
                }
            }
            UG.UiText {
                tag: "ui.pages.activitypopup.8"
                verticalAlignment: Text.AlignVCenter
                textKey: "activity.empty"
                visible: activity.clients.length === 0
                typographyRole: (true) ? "caption" : "body"
                font.pixelSize: Style.value(activity.appearance, "activityPopupPixelSize")
            }
            Rectangle {
                width: activityHeader.width
                Layout.topMargin: Style.value(activity.appearance, "activityPopupTopMargin")
                Layout.bottomMargin: Style.value(activity.appearance, "activityPopupBottomMargin")
                height: 1
                color: activity.appearance.border
            }
        }
        ListView {
            id: downloadsView
            objectName: "tasks.scroll"
            anchors.left: parent.left
            anchors.right: parent.right
            y: activityHeader.implicitHeight + activity.appearance.spacing
            height: Math.max(0, activity.availableHeight - y)
            clip: true
            spacing: activity.appearance.spacing
            model: Session.downloadModel
            function updateTaskLayout() {
                downloadsView.forceLayout()
            }
            onCountChanged: Qt.callLater(updateTaskLayout)
            onHeightChanged: Qt.callLater(updateTaskLayout)
            Connections {
                target: Session.downloadModel
                function onChanged() {
                    if (activity.visible)
                        downloadsView.forceLayout()
                }
            }
            QC.ScrollBar.vertical: UG.ScrollBar {
                tag: "ui.tasks.scrollbar"
            }
            delegate: Item {
                id: downloadRow
                width: Math.max(0, downloadsView.width - (downloadsView.contentHeight > downloadsView.height ? activity.appearance.scrollbarWidth : 0))
                required property var modelData
                height: implicitHeight
                objectName: "task.download." + modelData.id
                implicitHeight: modelData.state === "failed" ? failureContent.implicitHeight : operation.implicitHeight
                onImplicitHeightChanged: Qt.callLater(downloadsView.updateTaskLayout)
                ColumnLayout {
                    id: failureContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    visible: downloadRow.modelData.state === "failed"
                    spacing: activity.appearance.spacing
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: activity.appearance.spacing
                        TaskErrorIndicator {
                            objectName: "task.error." + downloadRow.modelData.id
                            tooltip: downloadRow.modelData.error
                        }
                        UG.UiText {
                            tag: "ui.download.failedTitle"
                            displayText: downloadRow.modelData.title
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                            wrapMode: Text.NoWrap
                        }
                        UG.Button {
                            id: retryButton
                            tag: "ui.download.retry"
                            objectName: "task.retry." + downloadRow.modelData.id
                            enabled: downloadRow.modelData.can_retry
                            textKey: "common.retry"
                            density: "compact"
                            implicitWidth: retryLabel.advanceWidth + 2 * appearance.controlPadding
                            TextMetrics {
                                id: retryLabel
                                font: retryButton.font
                                text: retryButton.text
                            }
                            onActivated: Session.command("retry_download", downloadRow.modelData.id)
                        }
                    }
                    UG.UiText {
                        tag: "ui.download.stopped"
                        textKey: "downloads.stopped"
                        stateKey: "danger"
                        typographyRole: "caption"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        elide: Text.ElideRight
                    }
                }
                UG.OperationRow {
                    id: operation
                    tag: "ui.download.row"
                    width: parent.width
                    readonly property var task: downloadRow.modelData
                    visible: task.state !== "failed"
                    expandable: false
                    paused: task.paused
                    stage: {
                        Session.locale
                        return task.state === "retrying" ? task.stage : [Session.formatDownloadSpeed(task.bytes_per_second), task.stage].filter(Boolean).join(" · ")
                    }
                    displayText: task.title
                    progress: Math.max(0, task.progress) / 100
                    stageProgress: Math.max(0, task.stage_progress) / 100
                    actionModel: [
                        {
                            key: "pause",
                            icon: IconSources[task.paused ? "play" : "pause"] || "",
                            explanation: Session.text(task.paused ? "downloads.resume" : "downloads.pause")
                        },
                        {
                            key: "cancel",
                            icon: IconSources["close"] || "",
                            explanation: Session.text("downloads.cancel")
                        }
                    ]
                    onActionRequested: action => Session.command(action === "pause" ? "pause_download" : "cancel_download", task.id)
                }
            }
        }
    }
    UG.ConfirmationDialog {
        id: killDialog
        objectName: "tasks.kill.confirm"
        parent: activity.dialogHost
        tag: "ui.pages.activitypopup.9"
        actions: [
            {
                key: "cancel",
                text_key: "common.cancel"
            },
            {
                key: "accept",
                text_key: "activity.kill",
                state_key: "danger"
            }
        ]
        defaultAction: "accept"
        cancelAction: "cancel"
        heading: Session.text("activity.kill_title")
        message: Session.text("activity.kill_hint")
        onActionRequested: action => {
            if (action === "accept")
                Session.command("kill_client", activity.clientId)
        }
    }
}
