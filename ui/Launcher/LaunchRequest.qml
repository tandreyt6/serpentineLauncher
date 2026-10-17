import "Style.js" as Style
import QtQuick
import Working.Gui as UG

FocusScope {
    id: request
    property string buildId: ""
    property string launchOrigin: "launcher"
    property bool running: { Session.builds; return !!Session.build(buildId).running }
    readonly property var coreState: {
        Session.buildCoreRevision
        return Session.buildCoreState(buildId)
    }
    readonly property bool installing: !running && coreState.progress >= 0
    readonly property bool needsInstall: !coreState.installed
    readonly property bool pendingChanges: !!coreState.pending_changes
    function requestLaunch(account) {
        if (!buildId.length || running || installing || coreState.syncing)
            return
        if (pendingChanges) {
            syncLoader.active = true
            if (syncLoader.item) {
                syncLoader.item.accountId = account
                syncLoader.item.targetId = buildId
                syncLoader.item.open()
            }
        } else
            Session.command("play", buildId, account, launchOrigin)
    }
    function requestPlay() {
        if (!buildId.length || running || installing || coreState.syncing)
            return
        if (needsInstall)
            Session.command("install_build", buildId)
        else
            requestLaunch("")
    }
    function requestStop() {
        if (buildId.length && running) {
            stopLoader.active = true
            if (stopLoader.item) {
                stopLoader.item.targetId = buildId
                stopLoader.item.open()
            }
        }
    }
    Loader {
        id: syncLoader
        active: false
        visible: false
        sourceComponent: Component {
            UG.ConfirmationDialog {
                parent: request.Window.window ? request.Window.window.contentItem : null
                width: Math.min(Style.value((request.Window.window ? request.Window.window.appearance : null), "buildActionsWidth"), Math.max(0, ownerWidth - Style.value((request.Window.window ? request.Window.window.appearance : null), "buildActionsWidth2")))
                tag: "ui.build.unsynced"
                objectName: "build.sync.dialog." + request.buildId
                property string accountId: ""
                property string targetId: ""
                heading: Session.text("builds.unsynced")
                actions: [
                    {key: "sync", text_key: "builds.sync_play", state_key: "primary"},
                    {key: "play", text_key: "builds.play_as_is"},
                    {key: "cancel", text_key: "common.cancel"}
                ]
                cancelAction: "cancel"
                defaultAction: "sync"
                onActionRequested: key => Session.command(key === "sync" ? "sync_and_play" : "play", targetId, accountId, request.launchOrigin)
            }
        }
    }
    Loader {
        id: stopLoader
        active: false
        visible: false
        sourceComponent: Component {
            UG.ConfirmationDialog {
                parent: request.Window.window ? request.Window.window.contentItem : null
                tag: "ui.build.stop.confirm"
                objectName: "build.stop.dialog." + request.buildId
                property string targetId: ""
                heading: Session.text("shortcuts.stop_heading")
                message: targetId.length ? Session.formatText("shortcuts.stop_message", {build: Session.build(targetId).title}) : ""
                actions: [
                    {key: "cancel", text_key: "common.cancel"},
                    {key: "stop", text_key: "shortcuts.stop", state_key: "danger"}
                ]
                cancelAction: "cancel"
                defaultAction: "cancel"
                onActionRequested: key => {
                    if (key === "stop" && Session.build(targetId).running)
                        Session.command("close_client", targetId)
                }
            }
        }
    }
}
