import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

RowLayout {
    id: bar
    required property var targetEditor
    visible: false
    function open() {
        visible = true
        query.forceActiveFocus()
        query.selectAll()
    }
    function findNext() {
        const match = Session.findDocument(targetEditor.document.document, query.text, targetEditor.selectionEnd)
        if (match.end !== undefined)
            targetEditor.editor.select(match.start, match.end)
    }
    UG.TextField {
        id: query
        objectName: "text.find.query"
        tag: "ui.text.find.query"
        textKey: "common.search"
        iconSource: IconSources["search"]
        Layout.fillWidth: true
        onAccepted: bar.findNext()
        Keys.onEscapePressed: event => { bar.visible = false; bar.targetEditor.editor.forceActiveFocus(); event.accepted = true }
    }
    UG.Button {
        tag: "ui.text.find.next"
        textKey: "shortcuts.find_next"
        onActivated: bar.findNext()
    }
    UG.ToolButton {
        tag: "ui.text.find.close"
        iconSource: IconSources["close"]
        displayText: ""
        useDisplayText: true
        tooltipKey: "shortcuts.find_close"
        implicitWidth: implicitHeight
        onActivated: { bar.visible = false; bar.targetEditor.editor.forceActiveFocus() }
    }
}
