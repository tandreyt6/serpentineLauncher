import "../Launcher/Style.js" as Style
import "../Launcher/ShortcutTargets.js" as Targets
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import QtQuick.Controls as QC
import "../pages" as Pages
import Launcher

Item {
    id: frame
    ToolTipPolicy {}
    objectName: "editor.body." + workspaceGroupKey
    required property var windowContext
    required property string workspaceGroupKey
    readonly property var buildData: {
        Session.builds
        return Session.build(windowContext.ownerKey)
    }
    readonly property bool dirty: (Session.dirtyEditors, Editors.structureRevision, Editors.buildDirty(windowContext.ownerKey))
    readonly property bool canSave: (Session.dirtyEditors, Session.builds, Editors.revision, Editors.canSaveBuild(windowContext.ownerKey))
    readonly property bool preparingUi: Editors.loadingKeys.includes(windowContext.selectedKey)
    ShortcutHost {
        id: shortcuts
        contextKey: "editor"
        enabled: !frame.preparingUi
        onTriggered: action => {
            const group = frame.workspaceGroupKey
            if (action === "quickSwitch")
                quickSwitch.open()
            else if (action === "launchBuild")
                launchActions.requestPlay()
            else if (action === "stopBuild")
                launchActions.requestStop()
            else if (action === "openFolder")
                Session.command("open_build_folder", frame.windowContext.ownerKey)
            else if (action === "tasks")
                activity.open()
            else if (action === "save" && frame.canSave)
                Editors.command("save_build", frame.windowContext.ownerKey, "")
            else if (action === "saveAll")
                Editors.saveAll()
            else if (action === "closeTab")
                Editors.requestCloseTab(frame.windowContext.selectedKey)
            else if (action === "nextTab" || action === "previousTab") {
                const tabs = Editors.tabs(group)
                const index = tabs.findIndex(tab => tab.key === frame.windowContext.selectedKey)
                if (tabs.length)
                    Editors.command("select", tabs[(index + (action === "nextTab" ? 1 : -1) + tabs.length) % tabs.length].key, "")
            } else if (!Targets.dispatch(Editors.currentPage(group), action) && action === "back")
                Lifecycle.showMain()
        }
    }
    Shortcut {
        sequence: "Esc"
        context: Qt.WindowShortcut
        enabled: !!frame.Window.window && frame.Window.window.active && !shortcuts.blocked && !frame.preparingUi && Editors.tabs(frame.workspaceGroupKey).some(tab => tab.key === frame.windowContext.selectedKey && (tab.kind === "catalog" || tab.kind === "mod"))
        onActivated: Targets.dispatch(Editors.currentPage(frame.workspaceGroupKey), "back")
    }
    DeferredPopup {
        id: quickSwitch
        source: ThemeUI.viewUrl("dialogs/QuickSwitchDialog.qml")
    }
    Pages.ActivityPopup {
        id: activity
        parent: QC.Overlay.overlay
        x: parent ? parent.width - width - appearance.pageMargin : 0
        y: parent ? parent.height - height - appearance.pageMargin : 0
    }
    LoadingIndicator {
        tag: "ui.editor.window.loading"
        objectName: "editor.window.loading"
        anchors.centerIn: parent
        visible: frame.preparingUi
        z: 10
    }
    ThemeBackground {
        tag: "ui.background.editor"
        objectName: "theme.background.editor"
        anchors.fill: parent
    }
    ColumnLayout {
        objectName: "editor.window.content"
        opacity: frame.preparingUi ? 0 : 1
        enabled: !frame.preparingUi
        anchors.fill: parent
        spacing: Style.value((frame.Window.window ? frame.Window.window.appearance : null), "editorWindowSpacing")
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Style.value((frame.Window.window ? frame.Window.window.appearance : null), "editorWindowMargins")
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value((frame.Window.window ? frame.Window.window.appearance : null), "editorWindowImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                tag: "ui.editor.return"
                stateKey: "secondary"
                textKey: "editor.return_launcher"
                iconSource: IconSources["back"] || ""
                onActivated: Lifecycle.showMain()
            }
            Item {
                Layout.fillWidth: true
            }
            UG.UiText {
                tag: "ui.editor.editorbuild.1"
                textKey: "editor.unsaved"
                opacity: frame.dirty ? 1 : 0
                Accessible.ignored: !frame.dirty
                typographyRole: "caption"
                font.pixelSize: Style.value((frame.Window.window ? frame.Window.window.appearance : null), "editorWindowPixelSize")
            }
            OpenFolderButton {
                tag: "ui.editor.build.folder"
                objectName: "editor.folder"
                buildId: frame.windowContext.ownerKey
            }
            UG.SplitButton {
                id: saveButton
                tag: "ui.editor.editorbuild.2"
                objectName: "editor.save"
                stateKey: "primary"
                textKey: "common.save"
                iconSource: IconSources["save"] || ""
                secondaryIconSource: IconSources["chevron-down"] || ""
                implicitWidth: Math.max(Style.value((frame.Window.window ? frame.Window.window.appearance : null), "editorWindowImplicitWidth"), saveMetrics.advanceWidth + 2 * appearance.controlPadding + appearance.iconSize + appearance.iconGap) + appearance.controlHeight + appearance.splitButtonGap
                TextMetrics {
                    id: saveMetrics
                    text: saveButton.caption
                    font.family: saveButton.appearance.fontFamily
                    font.pixelSize: saveButton.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                TextMetrics {
                    id: revertMetrics
                    text: Session.text("editor.revert")
                    font.family: saveButton.menu.appearance.fontFamily
                    font.pixelSize: saveButton.menu.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                Binding {
                    target: saveButton.menu
                    property: "width"
                    value: Math.min(saveButton.menu.appearance.popupWidth, Math.max(saveButton.width, Math.ceil(revertMetrics.advanceWidth) + Math.max(saveButton.menu.appearance.controlPadding, saveButton.primary.leftPadding) + Math.max(saveButton.menu.appearance.controlPadding, saveButton.primary.rightPadding) + saveButton.menu.appearance.optionCheckWidth + 2 * saveButton.menu.padding), saveButton.menu.constrainedToWindow && saveButton.menu.parent ? saveButton.menu.parent.width : Infinity)
                }
                Binding {
                    target: saveButton.menu
                    property: "height"
                    value: Math.min(saveButton.menu.appearance.popupHeight, saveButton.menu.appearance.controlHeight + 2 * saveButton.menu.padding, saveButton.menu.constrainedToWindow && saveButton.menu.parent ? saveButton.menu.parent.height : Infinity)
                }
                mainEnabled: frame.canSave
                secondaryEnabled: frame.dirty
                actions: [{key: "discard", text_key: "editor.revert", enabled: frame.dirty}]
                onActivated: Editors.command("save_build", frame.windowContext.ownerKey, "")
                onActionRequested: key => {
                    if (key === "discard" && frame.dirty)
                        Editors.command("discard_build", frame.windowContext.ownerKey, "")
                }
                Binding {
                    target: saveButton.primary
                    property: "disabledExplanation"
                    value: frame.buildData.running && Session.settings.safeMode ? Session.text("editor.blocked.settings") : ""
                }
            }
            BuildActions {
                id: launchActions
                launchOrigin: "editor"
                buildId: frame.windowContext.ownerKey
                running: !!frame.buildData.running
            }
        }
        UG.DetachableTabs {
            tag: "ui.editor.tabs"
            objectName: "editor.tabs." + frame.workspaceGroupKey
            groupKey: frame.workspaceGroupKey
            existingGroup: true
            preserveOnClose: true
            contentSized: true
            showDetachButton: Session.settings.editorShowDetachButton
            Layout.fillWidth: true
            Layout.fillHeight: true
            onPanelCloseRequested: key => Editors.requestCloseTab(key)
        }
    }
    UG.ConfirmationDialog {
        id: closeDialog
        tag: "ui.editor.unsaved"
        objectName: "editor.unsaved." + frame.workspaceGroupKey
        property string closingKey: ""
        heading: Session.text("editor.unsaved")
        message: Session.text("editor.unsaved_hint")
        actions: [
            {
                key: "cancel",
                text_key: "common.cancel"
            },
            {
                key: "discard",
                text_key: "editor.discard"
            },
            {
                key: "save",
                text_key: "common.save",
                state_key: "primary"
            }
        ]
        defaultAction: "save"
        cancelAction: "cancel"
        onActionRequested: key => Editors.command(key + (closingKey.length ? "_tab" : "_window"), closingKey.length ? closingKey : frame.workspaceGroupKey, "")
        onCancelled: Editors.cancelClose(frame.workspaceGroupKey)
    }
    ModQueueDialog {
        parent: frame.Window.window ? frame.Window.window.contentItem : null
        buildId: frame.windowContext.ownerKey
        workspaceKey: frame.workspaceGroupKey
    }
    Connections {
        target: Editors
        function onConfirmationRequested(group, key) {
            if (group === frame.workspaceGroupKey) {
                closeDialog.closingKey = key
                closeDialog.open()
            }
        }
    }
}
