import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

UG.ScrollArea {
    id: scroll
    tag: "settings.scroll.editorsettings"
    ColumnLayout {
        width: Math.max(0, scroll.width - scroll.appearance.scrollbarWidth - Style.value(scroll.appearance, "editorSettingsWidth"))
        spacing: Style.value(scroll.appearance, "editorSettingsSpacing")
        UG.Frame {
            tag: "settings.card.editor_navigation"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "editorSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.editor_navigation"
                    textKey: "settings.editor_navigation"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.editorDefaultSection"
                    textKey: "settings.editor_start"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: editorDefaultSectionChoice
                        density: "compact"
                        tag: "settings.control.editorDefaultSection"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "general",
                                    text: Session.text("editor.general")
                                },
                                {
                                    key: "java",
                                    text: Session.text("editor.java")
                                },
                                {
                                    key: "mods",
                                    text: Session.text("editor.mods")
                                },
                                {
                                    key: "packs",
                                    text: Session.text("editor.packs")
                                },
                                {
                                    key: "shaders",
                                    text: Session.text("editor.shaders")
                                },
                                {
                                    key: "configs",
                                    text: Session.text("editor.configs")
                                },
                                {
                                    key: "files",
                                    text: Session.text("editor.files")
                                },
                                {
                                    key: "logs",
                                    text: Session.text("editor.logs")
                                },
                                {
                                    key: "worlds",
                                    text: Session.text("editor.worlds")
                                }
                            ]
                        }
                        selectedKey: Session.settings.editorDefaultSection
                        onSelectionRequested: key => Session.command("setting", "editorDefaultSection", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.editorShowDetachButton"
                    textKey: "settings.editor_detach_button"
                    Layout.fillWidth: true
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "editorSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "editorSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "editorSettingsRightMargin")
                        tag: "settings.control.editorShowDetachButton"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.editorShowDetachButton
                        onClicked: Session.command("setting", "editorShowDetachButton", (!Session.settings.editorShowDetachButton).toString())
                    }
                }
                UG.FormRow {
                    tag: "settings.row.editorDetachDistance"
                    textKey: "settings.detach_distance"
                    Layout.fillWidth: true
                    UG.TextField {
                        tag: "settings.control.editorDetachDistance"
                        displayText: ""
                        useDisplayText: true
                        Layout.preferredWidth: Style.value(scroll.appearance, "editorSettingsPreferredWidth")
                        Layout.alignment: Qt.AlignRight
                        text: Session.settings.editorDetachDistance
                        suffixText: Session.text("common.px")
                        validator: IntValidator {
                            bottom: 5
                            top: 300
                        }
                        onEditingFinished: {
                            Session.command("setting", "editorDetachDistance", text)
                            text = Qt.binding(function () {
                                return Session.settings.editorDetachDistance
                            })
                        }
                    }
                }
            }
        }
        UG.Frame {
            tag: "settings.card.text_editor"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "editorSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.text_editor"
                    textKey: "settings.text_editor"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.editorWrap"
                    textKey: "settings.wrap_lines"
                    Layout.fillWidth: true
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "editorSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "editorSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "editorSettingsRightMargin")
                        tag: "settings.control.editorWrap"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.editorWrap
                        onClicked: Session.command("setting", "editorWrap", (!Session.settings.editorWrap).toString())
                    }
                }
                UG.FormRow {
                    tag: "settings.row.editorLineNumbers"
                    textKey: "settings.line_numbers"
                    Layout.fillWidth: true
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "editorSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "editorSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "editorSettingsRightMargin")
                        tag: "settings.control.editorLineNumbers"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.editorLineNumbers
                        onClicked: Session.command("setting", "editorLineNumbers", (!Session.settings.editorLineNumbers).toString())
                    }
                }
                UG.FormRow {
                    tag: "settings.row.editorHighlighting"
                    textKey: "settings.syntax_highlighting"
                    Layout.fillWidth: true
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "editorSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "editorSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "editorSettingsRightMargin")
                        tag: "settings.control.editorHighlighting"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.editorHighlighting
                        onClicked: Session.command("setting", "editorHighlighting", (!Session.settings.editorHighlighting).toString())
                    }
                }
            }
        }
    }
}
