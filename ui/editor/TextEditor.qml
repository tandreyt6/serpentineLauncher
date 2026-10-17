import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher.Native
import Launcher

Item {
    id: page
    required property string buildId
    required property string workspaceKey
    required property string tabKey
    required property string filePath
    required property var documentBuffer
    readonly property bool dirty: documentBuffer.dirty
    readonly property bool protectedBuild: {
        Session.builds
        return !!Session.build(buildId).running && Session.settings.safeMode
    }
    readonly property bool canSave: dirty && !protectedBuild
    onCanSaveChanged: {
        if (tabKey)
            Editors.reportSaveState(tabKey, canSave)
    }
    Component.onCompleted: Editors.reportSaveState(tabKey, canSave)
    objectName: "editor.file." + tabKey
    function save() {
        if (canSave)
            documentBuffer.requestSave()
    }
    function discard() {
        documentBuffer.reset(tabKey, Editors.savedText(tabKey), documentBuffer.revision + 1)
    }
    function handleShortcut(action) {
        if (action === "find") {
            findBar.open()
            return true
        }
        return false
    }
    onDirtyChanged: Session.command("editor_dirty", tabKey, dirty.toString())
    Connections {
        target: Session
        function onEditorSaveRequested(key) {
            if (key === page.tabKey || key === "*")
                page.save()
        }
        function onEditorDiscardRequested(key) {
            if (key === page.tabKey || key === "*")
                page.discard()
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: editor.appearance.pageMargin
        spacing: Style.value((page.Window.window ? page.Window.window.appearance : null), "textEditorSpacing")
        RowLayout {
            Layout.fillWidth: true
            UG.UiText {
                tag: "ui.file.path"
                Layout.fillWidth: true
                displayText: page.filePath
                typographyRole: "caption"
                wrapMode: Text.NoWrap
                elide: Text.ElideLeft
            }
        }
        TextFindBar {
            id: findBar
            targetEditor: editor
            Layout.fillWidth: true
        }
        UG.TextEditor {
            id: editor
            tag: "ui.file.editor"
            objectName: "editor.configText." + page.tabKey
            Layout.fillWidth: true
            Layout.fillHeight: true
            document: page.documentBuffer
            Binding { target: editor.editor.Keys; property: "enabled"; value: false }
            wrap: Session.settings.editorWrap
            lineNumbers: Session.settings.editorLineNumbers
            ConfigHighlighter {
                document: page.documentBuffer.document
                colors: [editor.appearance.accent, editor.appearance.muted, editor.appearance.foreground]
                enabled: Session.settings.editorHighlighting
            }
        }
    }
}
