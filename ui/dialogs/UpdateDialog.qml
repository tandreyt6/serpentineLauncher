import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import Working.Gui as UG

UG.PopupPanel {
    id: dialog
    parent: QC.Overlay.overlay
    objectName: "updates.dialog"
    tag: "ui.updates.dialog"
    width: Math.min(520, parent ? parent.width - 32 : 520)
    height: Math.min(updateContent.implicitHeight + topPadding + bottomPadding,
        parent ? parent.height - 2 * padding : updateContent.implicitHeight + topPadding + bottomPadding)
    anchors.centerIn: parent
    modal: true
    focus: true
    closePolicy: QC.Popup.NoAutoClose
    onClosed: Updates.dismissStartup()
    background: UG.Frame {
        tag: "ui.updates.surface"
        padding: 0
        displayText: ""
        useDisplayText: true
    }
    contentItem: ColumnLayout {
        id: updateContent
        spacing: dialog.appearance.spacing
        UG.UiText {
            tag: "ui.updates.heading"
            Layout.fillWidth: true
            textKey: "updates.heading"
            font.weight: Font.DemiBold
        }
        UG.UiText {
            tag: "ui.updates.message"
            objectName: "updates.message"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            displayText: {
                Session.revision
                let value = Session.text("updates." + Updates.status).replace("%version%", Updates.version)
                if (Updates.status === "available" && !Updates.installable)
                    value += "\n\n" + Session.text("updates.source_mode")
                if (Updates.status === "blocked")
                    value += "\n" + Updates.blockers.map(key => Session.text(key)).join("\n")
                if (Updates.error.length)
                    value += "\n\n" + Updates.error
                return value
            }
            useDisplayText: true
        }
        UG.ProgressBar {
            tag: "ui.updates.progress"
            objectName: "updates.progress"
            Layout.fillWidth: true
            visible: Updates.status === "downloading" || Updates.status === "waiting" || Updates.status === "checking"
            indeterminate: Updates.status !== "downloading"
            value: Updates.progress
        }
        UG.CheckBox {
            tag: "ui.updates.never_again"
            objectName: "updates.neverAgain"
            Layout.fillWidth: true
            visible: Updates.startupPrompt && Updates.status === "available"
            textKey: "updates.never_again"
            checkable: false
            checked: !Session.settings.startupUpdatePrompt
            onClicked: Session.command("setting", "startupUpdatePrompt", (!Session.settings.startupUpdatePrompt).toString())
        }
        UG.UiText {
            tag: "ui.updates.percent"
            Layout.alignment: Qt.AlignRight
            visible: Updates.status === "downloading"
            displayText: Math.round(Updates.progress * 100) + "%"
            useDisplayText: true
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            UG.Button {
                tag: "ui.updates.later"
                textKey: Updates.startupPrompt || Updates.status === "blocked" || Updates.status === "waiting" || Updates.status === "ready" ? "updates.later" : "common.close"
                onActivated: {
                    if (["blocked", "waiting", "ready"].indexOf(Updates.status) >= 0)
                        Lifecycle.resolveUpdate("later")
                    dialog.close()
                }
            }
            UG.Button {
                tag: "ui.updates.install"
                objectName: "updates.install"
                textKey: Updates.status === "blocked" ? "updates.close_continue" : "updates.install"
                stateKey: "primary"
                visible: Updates.installable && ["available", "ready", "deferred", "blocked"].indexOf(Updates.status) >= 0
                onActivated: {
                    if (Updates.status === "blocked")
                        Lifecycle.resolveUpdate("continue")
                    else
                        Updates.install()
                }
            }
        }
    }
}
