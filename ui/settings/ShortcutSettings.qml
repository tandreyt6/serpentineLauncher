import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import Working.Gui as UG
import "../Launcher/Style.js" as Style

UG.ScrollArea {
    id: page
    tag: "ui.settings.shortcuts"
    objectName: "settings.shortcuts.form"
    clip: true
    contentWidth: width
    ColumnLayout {
        width: Math.max(0, page.width - page.appearance.scrollbarWidth - page.appearance.smallGap)
        spacing: page.appearance.layoutGap
        Repeater {
            model: ["shared", "main", "editor", "palette"]
            delegate: ColumnLayout {
                id: group
                required property string modelData
                Layout.fillWidth: true
                spacing: page.appearance.smallGap
                UG.UiText {
                    tag: "ui.settings.shortcuts.group"
                    textKey: "shortcuts.context." + group.modelData
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                Repeater {
                    model: Session.shortcutActions.filter(action => (action.scopes.length > 1 ? "shared" : action.scopes[0]) === group.modelData)
                    delegate: GridLayout {
                        id: row
                        required property var modelData
                        Layout.fillWidth: true
                        columns: width < 2 * page.appearance.fieldWidth ? 2 : 3
                        UG.UiText {
                            tag: "ui.settings.shortcuts.action"
                            textKey: "shortcuts.action." + row.modelData.key
                            Layout.fillWidth: true
                            Layout.columnSpan: row.columns === 2 ? 2 : 1
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                            wrapMode: Text.NoWrap
                        }
                        UG.Button {
                            tag: "ui.settings.shortcuts.binding"
                            objectName: "settings.shortcut." + row.modelData.key
                            displayText: {
                                Session.locale
                                const sequence = Session.settings["shortcut." + row.modelData.key]
                                return sequence.length ? Session.shortcutLabel(sequence) : Session.text("shortcuts.unassigned")
                            }
                            useDisplayText: true
                            implicitWidth: page.appearance.fieldWidth
                            Layout.fillWidth: row.columns === 2
                            Layout.minimumWidth: 0
                            onActivated: capture.begin(row.modelData.key, Session.settings["shortcut." + row.modelData.key])
                        }
                        UG.ToolButton {
                            tag: "ui.settings.shortcuts.reset"
                            objectName: "settings.shortcut.reset." + row.modelData.key
                            iconSource: IconSources["refresh"]
                            tooltipKey: "shortcuts.reset"
                            displayText: ""
                            useDisplayText: true
                            implicitWidth: implicitHeight
                            enabled: Session.settings["shortcut." + row.modelData.key] !== row.modelData.default
                            onActivated: capture.begin(row.modelData.key, row.modelData.default)
                        }
                    }
                }
            }
        }
    }
    UG.PopupPanel {
        id: capture
        tag: "ui.settings.shortcuts.capture"
        objectName: "settings.shortcuts.capture"
        parent: QC.Overlay.overlay
        modal: true
        focus: true
        padding: page.appearance.dialogPadding
        width: Math.min(Style.value(page.appearance, "shortcutCaptureWidth"), parent ? parent.width - 2 * page.appearance.pageMargin : Style.value(page.appearance, "shortcutCaptureWidth"))
        height: contentItem.implicitHeight + topPadding + bottomPadding
        x: parent ? (parent.width - width) / 2 : 0
        y: parent ? (parent.height - height) / 2 : 0
        background: UG.Frame {
            tag: "ui.settings.shortcuts.capture.surface"
            objectName: "settings.shortcuts.capture.surface"
            padding: 0
            displayText: ""
            useDisplayText: true
        }
        property string actionKey: ""
        property string candidate: ""
        readonly property var validation: {
            Session.settings
            return Session.checkShortcut(actionKey, candidate)
        }
        function begin(action, sequence) {
            actionKey = action
            candidate = sequence
            open()
        }
        function apply() {
            if (validation.valid && Session.assignShortcut(actionKey, validation.sequence))
                close()
        }
        onOpened: recorder.forceActiveFocus()
        contentItem: ColumnLayout {
            spacing: page.appearance.layoutGap
            UG.UiText {
                tag: "ui.settings.shortcuts.capture.title"
                textKey: capture.actionKey.length ? "shortcuts.action." + capture.actionKey : "settings.shortcuts"
                typographyRole: "heading"
                Layout.fillWidth: true
            }
            FocusScope {
                id: recorder
                objectName: "settings.shortcuts.recorder"
                Layout.fillWidth: true
                implicitHeight: sequenceLabel.implicitHeight + 2 * page.appearance.controlPadding
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Escape) {
                        capture.close()
                    } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && event.modifiers === Qt.NoModifier) {
                        capture.apply()
                    } else if ((event.key === Qt.Key_Backspace || event.key === Qt.Key_Delete) && event.modifiers === Qt.NoModifier) {
                        capture.candidate = ""
                    } else {
                        const sequence = Session.shortcutFromKey(event.key, event.modifiers)
                        if (sequence.length)
                            capture.candidate = sequence
                    }
                    event.accepted = true
                }
                UG.UiText {
                    id: sequenceLabel
                    tag: "ui.settings.shortcuts.capture.sequence"
                    anchors.centerIn: parent
                    displayText: capture.candidate.length ? Session.shortcutLabel(capture.candidate) : Session.text("shortcuts.unassigned")
                    useDisplayText: true
                    font.pixelSize: page.appearance.sectionSize
                }
            }
            UG.UiText {
                tag: "ui.settings.shortcuts.capture.hint"
                textKey: "shortcuts.press"
                Layout.fillWidth: true
            }
            UG.UiText {
                tag: "ui.settings.shortcuts.capture.error"
                objectName: "settings.shortcuts.error"
                Layout.fillWidth: true
                visible: !capture.validation.valid
                color: page.appearance.danger
                displayText: {
                    Session.locale
                    if (capture.validation.conflicts.length)
                        return Session.formatText("shortcuts.conflict", {actions: capture.validation.conflicts.map(key => Session.text("shortcuts.action." + key)).join(", ")})
                    return capture.validation.error.length ? Session.text(capture.validation.error) : ""
                }
                useDisplayText: true
            }
            RowLayout {
                Layout.fillWidth: true
                UG.Button {
                    tag: "ui.settings.shortcuts.capture.clear"
                    objectName: "settings.shortcuts.clear"
                    textKey: "shortcuts.disable"
                    onActivated: { capture.candidate = ""; recorder.forceActiveFocus() }
                }
                Item { Layout.fillWidth: true }
                UG.Button {
                    tag: "ui.settings.shortcuts.capture.cancel"
                    textKey: "common.cancel"
                    onActivated: capture.close()
                }
                UG.Button {
                    tag: "ui.settings.shortcuts.capture.apply"
                    objectName: "settings.shortcuts.apply"
                    textKey: "editor.apply_filters"
                    stateKey: "primary"
                    enabled: capture.validation.valid
                    onActivated: capture.apply()
                }
            }
        }
    }
}
