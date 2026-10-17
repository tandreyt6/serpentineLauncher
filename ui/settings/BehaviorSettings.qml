import "../Launcher/Style.js" as Style
import QtQuick
import Working.Gui as UG
import QtQuick.Layouts
import QtQuick.Controls as QC
import Launcher

UG.ScrollArea {
    id: scroll
    tag: "ui.scroll.behaviorsettings.0"
    clip: true
    contentWidth: width

    ColumnLayout {
        width: scroll.width
        spacing: layoutStyle.appearance.layoutGap
        UG.Frame {
            id: layoutStyle

            tag: "ui.settings.behaviorsettings.1"
            padding: 0
            displayText: ""
            useDisplayText: true

            Layout.fillWidth: true
            implicitHeight: lifecycle.implicitHeight + 2 * layoutStyle.appearance.cardPadding
            ColumnLayout {
                id: lifecycle
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: layoutStyle.appearance.cardPadding
                spacing: layoutStyle.appearance.layoutGap
                UG.UiText {
                    tag: "ui.settings.behaviorsettings.2"
                    verticalAlignment: Text.AlignVCenter
                    textKey: "settings.lifecycle"
                    font.pixelSize: layoutStyle.appearance.sectionSize
                    font.weight: Font.DemiBold
                }
                UG.FormRow {
                    tag: "ui.settings.behaviorsettings.3"
                    Layout.fillWidth: true
                    textKey: "settings.on_close"
                    UG.ComboBox {
                        id: selection0
                        density: "compact"
                        tag: "ui.settings.behaviorsettings.4"
                        valueRole: "key"
                        textRole: "text"
                        secondaryRole: "secondary"
                        Layout.preferredWidth: Style.value(scroll.appearance, "behaviorSettingsPreferredWidth")
                        model: {
                            const options = (function () {
                                    Session.revision
                                    return ["tray", "exit"].map(v => ({
                                                value: v,
                                                label: Session.text("settings." + v)
                                            }))
                                })()
                            return options.map(option => ({
                                        key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                        text: option.label === undefined ? option.text : option.label,
                                        secondary: option.note || option.secondary || "",
                                        pinned: !!option.pinned,
                                        enabled: option.enabled !== false
                                    }))
                        }
                        selectedKey: (Session.settings.closeAction) || "__all__"
                        onSelectionRequested: selected => {
                            const value = selected === "__all__" ? "" : selected
                            Session.command("setting", "closeAction", value)
                        }
                    }
                }
                UG.FormRow {
                    tag: "ui.settings.behaviorsettings.5"
                    Layout.fillWidth: true
                    textKey: "settings.on_launch"
                    UG.ComboBox {
                        id: selection1
                        density: "compact"
                        tag: "ui.settings.behaviorsettings.6"
                        valueRole: "key"
                        textRole: "text"
                        secondaryRole: "secondary"
                        Layout.preferredWidth: Style.value(scroll.appearance, "behaviorSettingsPreferredWidth")
                        model: {
                            const options = (function () {
                                    Session.revision
                                    return ["nothing", "minimize", "hide"].map(v => ({
                                                value: v,
                                                label: Session.text("settings." + v)
                                            }))
                                })()
                            return options.map(option => ({
                                        key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                        text: option.label === undefined ? option.text : option.label,
                                        secondary: option.note || option.secondary || "",
                                        pinned: !!option.pinned,
                                        enabled: option.enabled !== false
                                    }))
                        }
                        selectedKey: (Session.settings.launchAction) || "__all__"
                        onSelectionRequested: selected => {
                            const value = selected === "__all__" ? "" : selected
                            Session.command("setting", "launchAction", value)
                        }
                    }
                }
                UG.FormRow {
                    tag: "ui.settings.behaviorsettings.7"
                    Layout.fillWidth: true
                    textKey: "settings.on_finish"
                    UG.ComboBox {
                        id: selection2
                        density: "compact"
                        tag: "ui.settings.behaviorsettings.8"
                        valueRole: "key"
                        textRole: "text"
                        secondaryRole: "secondary"
                        Layout.preferredWidth: Style.value(scroll.appearance, "behaviorSettingsPreferredWidth")
                        model: {
                            const options = (function () {
                                    Session.revision
                                    return ["last", "each", "nothing"].map(v => ({
                                                value: v,
                                                label: Session.text("settings." + v)
                                            }))
                                })()
                            return options.map(option => ({
                                        key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                        text: option.label === undefined ? option.text : option.label,
                                        secondary: option.note || option.secondary || "",
                                        pinned: !!option.pinned,
                                        enabled: option.enabled !== false
                                    }))
                        }
                        selectedKey: (Session.settings.finishAction) || "__all__"
                        onSelectionRequested: selected => {
                            const value = selected === "__all__" ? "" : selected
                            Session.command("setting", "finishAction", value)
                        }
                    }
                }
            }
        }
        UG.Frame {
            tag: "ui.settings.behaviorsettings.9"
            padding: 0
            displayText: ""
            useDisplayText: true

            Layout.fillWidth: true
            implicitHeight: safety.implicitHeight + 2 * layoutStyle.appearance.cardPadding
            ColumnLayout {
                id: safety
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: layoutStyle.appearance.cardPadding
                spacing: layoutStyle.appearance.layoutGap
                UG.UiText {
                    tag: "ui.settings.behaviorsettings.10"
                    verticalAlignment: Text.AlignVCenter
                    textKey: "settings.safety"
                    font.pixelSize: layoutStyle.appearance.sectionSize
                    font.weight: Font.DemiBold
                }
                UG.FormRow {
                    tag: "ui.settings.behaviorsettings.11"
                    Layout.fillWidth: true
                    textKey: "settings.safe"
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "behaviorSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "behaviorSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "behaviorSettingsRightMargin")
                        tag: "ui.settings.behaviorsettings.12"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.safeMode
                        Accessible.name: Session.text("settings.safe")
                        onClicked: {
                            if (Session.settings.safeMode)
                                safeDialog.open()
                            else
                                Session.command("setting", "safeMode", "true")
                        }
                    }
                }
                UG.FormRow {
                    tag: "ui.settings.behaviorsettings.13"
                    Layout.fillWidth: true
                    textKey: "settings.drop"
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "behaviorSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "behaviorSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "behaviorSettingsRightMargin")
                        tag: "ui.settings.behaviorsettings.14"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.modDrop
                        Accessible.name: Session.text("settings.drop")
                        onClicked: Session.command("setting", "modDrop", (!Session.settings.modDrop).toString())
                    }
                }
            }
        }
    }
    UG.ConfirmationDialog {
        id: safeDialog
        tag: "ui.settings.behaviorsettings.21"
        actions: [
            {
                key: "cancel",
                text_key: "common.cancel"
            },
            {
                key: "accept",
                text_key: "common.confirm",
                state_key: "danger"
            }
        ]
        defaultAction: "accept"
        cancelAction: "cancel"
        heading: Session.text("settings.safe_warning")
        message: Session.text("settings.safe_warning_text")
        onActionRequested: action => {
            if (action === "accept")
                Session.command("setting", "safeMode", "false")
        }
    }
}
