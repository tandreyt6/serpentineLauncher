import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

UG.ScrollArea {
    id: scroll
    tag: "settings.scroll.loggingsettings"
    ColumnLayout {
        width: Math.max(0, scroll.width - scroll.appearance.scrollbarWidth - Style.value(scroll.appearance, "loggingSettingsWidth"))
        spacing: Style.value(scroll.appearance, "loggingSettingsSpacing")
        UG.Frame {
            tag: "settings.card.logging"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "loggingSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.logging"
                    textKey: "settings.logging"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.logMode"
                    textKey: "settings.log_mode"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: logModeChoice
                        density: "compact"
                        tag: "settings.control.logMode"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "normal",
                                    text: Session.text("settings.normal")
                                },
                                {
                                    key: "verbose",
                                    text: Session.text("settings.verbose")
                                }
                            ]
                        }
                        selectedKey: Session.settings.logMode
                        onSelectionRequested: key => Session.command("setting", "logMode", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.zipBatch"
                    textKey: "settings.zip"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: zipBatchChoice
                        density: "compact"
                        tag: "settings.control.zipBatch"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "5",
                                    text: Session.text("settings.five_files")
                                },
                                {
                                    key: "10",
                                    text: Session.text("settings.ten_files")
                                }
                            ]
                        }
                        selectedKey: Session.settings.zipBatch
                        onSelectionRequested: key => Session.command("setting", "zipBatch", key)
                    }
                }
            }
        }
        UG.Frame {
            tag: "settings.card.log_viewer"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "loggingSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.log_viewer"
                    textKey: "settings.log_viewer"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.logWrap"
                    textKey: "settings.wrap_lines"
                    Layout.fillWidth: true
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "loggingSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "loggingSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "loggingSettingsRightMargin")
                        tag: "settings.control.logWrap"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.logWrap
                        onClicked: Session.command("setting", "logWrap", (!Session.settings.logWrap).toString())
                    }
                }
                UG.FormRow {
                    tag: "settings.row.logFollowTail"
                    textKey: "settings.follow_tail"
                    Layout.fillWidth: true
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "loggingSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "loggingSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "loggingSettingsRightMargin")
                        tag: "settings.control.logFollowTail"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.logFollowTail
                        onClicked: Session.command("setting", "logFollowTail", (!Session.settings.logFollowTail).toString())
                    }
                }
            }
        }
    }
}
