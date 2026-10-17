import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

UG.ScrollArea {
    id: scroll
    tag: "settings.scroll.panelsettings"
    property bool showPreviewAction: true
    readonly property bool horizontalPanel: Session.settings.panelSide === "top" || Session.settings.panelSide === "bottom"
    signal livePreviewRequested()
    ColumnLayout {
        width: Math.max(0, scroll.width - scroll.appearance.scrollbarWidth - Style.value(scroll.appearance, "panelSettingsWidth"))
        spacing: Style.value(scroll.appearance, "panelSettingsSpacing")
        UG.Button {
            tag: "settings.panel.preview"
            objectName: "settings.panel.preview"
            textKey: "settings.panel_live"
            stateKey: "secondary"
            visible: scroll.showPreviewAction
            Layout.fillWidth: true
            onActivated: scroll.livePreviewRequested()
        }
        UG.Frame {
            tag: "settings.card.panel_position"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "panelSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.panel_position"
                    textKey: "settings.panel_position"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.panelSide"
                    textKey: "settings.panel_side"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: panelSideChoice
                        objectName: "settings.panelSide"
                        density: "compact"
                        tag: "settings.control.panelSide"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "left",
                                    text: Session.text("settings.left")
                                },
                                {
                                    key: "right",
                                    text: Session.text("settings.right")
                                },
                                {
                                    key: "top",
                                    text: Session.text("settings.top")
                                },
                                {
                                    key: "bottom",
                                    text: Session.text("settings.bottom")
                                }
                            ]
                        }
                        selectedKey: Session.settings.panelSide
                        onSelectionRequested: key => Session.command("setting", "panelSide", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.panelAlign"
                    visible: !scroll.horizontalPanel
                    textKey: "settings.panel_align"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: panelAlignChoice
                        objectName: "settings.panelAlign"
                        density: "compact"
                        tag: "settings.control.panelAlign"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "center",
                                    text: Session.text("settings.center")
                                },
                                {
                                    key: "top",
                                    text: Session.text("settings.top")
                                }
                            ]
                        }
                        selectedKey: Session.settings.panelAlign
                        onSelectionRequested: key => Session.command("setting", "panelAlign", key)
                    }
                }
            }
        }
        UG.Frame {
            tag: "settings.card.panel_interaction"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "panelSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.panel_interaction"
                    textKey: "settings.panel_interaction"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.panelMode"
                    visible: !scroll.horizontalPanel
                    textKey: "settings.panel_mode"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: panelModeChoice
                        objectName: "settings.panelMode"
                        density: "compact"
                        tag: "settings.control.panelMode"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "hover",
                                    text: Session.text("settings.hover")
                                },
                                {
                                    key: "button",
                                    text: Session.text("settings.button")
                                },
                                {
                                    key: "open",
                                    text: Session.text("settings.always_open")
                                },
                                {
                                    key: "closed",
                                    text: Session.text("settings.always_closed")
                                },
                                {
                                    key: "both",
                                    text: Session.text("settings.hover_button")
                                }
                            ]
                        }
                        selectedKey: Session.settings.panelMode
                        onSelectionRequested: key => Session.command("setting", "panelMode", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.panelLabels"
                    textKey: "settings.panel_labels"
                    visible: scroll.horizontalPanel
                    Layout.fillWidth: true
                    UG.ComboBox {
                        objectName: "settings.panelLabels"
                        tag: "settings.control.panelLabels"
                        density: "compact"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {key: "icons", text: Session.text("settings.panel_icons")},
                                {key: "text", text: Session.text("settings.panel_icons_text")}
                            ]
                        }
                        selectedKey: Session.settings.panelLabels
                        onSelectionRequested: key => Session.command("setting", "panelLabels", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.panelLayout"
                    visible: !scroll.horizontalPanel
                    textKey: "settings.panel_layout"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: panelLayoutChoice
                        objectName: "settings.panelLayout"
                        density: "compact"
                        tag: "settings.control.panelLayout"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "overlay",
                                    text: Session.text("settings.overlay")
                                },
                                {
                                    key: "push",
                                    text: Session.text("settings.push")
                                }
                            ]
                        }
                        selectedKey: Session.settings.panelLayout
                        onSelectionRequested: key => Session.command("setting", "panelLayout", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.panelHoverCloseMs"
                    visible: !scroll.horizontalPanel
                    textKey: "settings.panel_hover_close"
                    Layout.fillWidth: true
                    UG.TextField {
                        tag: "settings.control.panelHoverCloseMs"
                        objectName: "settings.panelHoverCloseMs"
                        displayText: ""
                        useDisplayText: true
                        Layout.preferredWidth: Style.value(scroll.appearance, "panelSettingsPreferredWidth")
                        Layout.alignment: Qt.AlignRight
                        text: Session.settings.panelHoverCloseMs
                        suffixText: Session.text("common.ms")
                        validator: IntValidator {
                            bottom: 0
                            top: 5000
                        }
                        onEditingFinished: {
                            if (acceptableInput)
                                Session.command("setting", "panelHoverCloseMs", text)
                            text = Qt.binding(function () { return Session.settings.panelHoverCloseMs })
                        }
                    }
                }
                UG.FormRow {
                    tag: "settings.row.panelAnimationMs"
                    textKey: "settings.panel_animation"
                    Layout.fillWidth: true
                    UG.TextField {
                        tag: "settings.control.panelAnimationMs"
                        displayText: ""
                        useDisplayText: true
                        Layout.preferredWidth: Style.value(scroll.appearance, "panelSettingsPreferredWidth")
                        Layout.alignment: Qt.AlignRight
                        text: Session.settings.panelAnimationMs
                        suffixText: Session.text("common.ms")
                        validator: IntValidator {
                            bottom: 0
                            top: 1000
                        }
                        onEditingFinished: {
                            Session.command("setting", "panelAnimationMs", text)
                            text = Qt.binding(function () {
                                return Session.settings.panelAnimationMs
                            })
                        }
                    }
                }
            }
        }
    }
}
