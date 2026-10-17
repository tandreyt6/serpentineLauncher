import "../Launcher/Style.js" as Style
import QtQuick
import Working.Gui as UG
import QtQuick.Layouts
import QtQuick.Controls as QC
import Launcher

UG.PopupPanel {
    id: dialog
    height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, parent ? parent.height : Style.value(dialog.appearance, "deleteBuildDialogHeight"))
    tag: "ui.dialogs.deletebuilddialog.1"
    property string buildId: ""
    property string buildTitle: ""
    property string deleteMode: "entry"
    modal: true
    focus: true
    anchors.centerIn: QC.Overlay.overlay
    width: Style.value(dialog.appearance, "deleteBuildDialogWidth")
    padding: dialog.appearance.dialogPadding
    closePolicy: QC.Popup.CloseOnEscape
    background: UG.Frame {
        tag: "ui.dialogs.deletebuilddialog.2"
        padding: 0
        displayText: ""
        useDisplayText: true
    }
    contentItem: ColumnLayout {
        spacing: dialog.appearance.layoutGap
        UG.UiText {
            tag: "ui.dialogs.deletebuilddialog.3"
            verticalAlignment: Text.AlignVCenter
            textKey: "builds.delete_title"
            font.pixelSize: Style.value(dialog.appearance, "deleteBuildDialogPixelSize")
            font.weight: Font.DemiBold
        }
        UG.UiText {
            tag: "ui.dialogs.deletebuilddialog.4"
            verticalAlignment: Text.AlignVCenter
            Layout.fillWidth: true
            displayText: dialog.buildTitle
            color: dialog.appearance.accent
        }
        UG.UiText {
            tag: "ui.dialogs.deletebuilddialog.5"
            verticalAlignment: Text.AlignVCenter
            Layout.fillWidth: true
            textKey: "builds.delete_hint"
            typographyRole: (true) ? "caption" : "body"
        }
        UG.ComboBox {
            id: selection0
            density: "compact"
            tag: "ui.dialogs.deletebuilddialog.6"
            valueRole: "key"
            textRole: "text"
            secondaryRole: "secondary"
            Layout.fillWidth: true
            model: {
                const options = (function () {
                        Session.revision
                        return [
                            {
                                value: "entry",
                                label: Session.text("builds.entry_only")
                            },
                            {
                                value: "files",
                                label: Session.text("builds.with_files")
                            }
                        ]
                    })()
                return options.map(option => ({
                            key: String(option.value === undefined ? option.key : option.value) || "__all__",
                            text: option.label === undefined ? option.text : option.label,
                            secondary: option.note || option.secondary || "",
                            pinned: !!option.pinned,
                            enabled: option.enabled !== false
                        }))
            }
            selectedKey: (dialog.deleteMode) || "__all__"
            onSelectionRequested: selected => {
                const value = selected === "__all__" ? "" : selected
                dialog.deleteMode = value
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value(dialog.appearance, "deleteBuildDialogImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.dialogs.deletebuilddialog.7"
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
                    }["common.cancel"] || ""] || ""
                textKey: "common.cancel"
                onClicked: dialog.close()
            }
            UG.Button {
                id: button1
                implicitWidth: Math.max(Style.value(dialog.appearance, "deleteBuildDialogImplicitWidth"), metrics1.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics1
                    text: button1.text
                    font.family: button1.appearance.fontFamily
                    font.pixelSize: button1.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.dialogs.deletebuilddialog.8"
                stateKey: (true) ? "primary" : "secondary"
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
                    }["common.delete"] || ""] || ""
                textKey: "common.delete"
                onClicked: {
                    dialog.close()
                    Session.command("delete", dialog.buildId, dialog.deleteMode)
                }
            }
        }
    }
}
