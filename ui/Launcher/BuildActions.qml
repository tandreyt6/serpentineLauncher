import "Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

LaunchRequest {
    id: launchActions
    objectName: "build.play." + buildId
    property bool compact: false
    property bool fillWidth: false
    implicitWidth: Style.value((launchActions.Window.window ? launchActions.Window.window.appearance : null), "buildActionsImplicitWidth")
    implicitHeight: split.implicitHeight
    UG.SplitButton {
        id: split
        tag: "ui.build.launch"
        objectName: "build.primary." + launchActions.buildId
        anchors.fill: parent
        visible: !launchActions.installing
        stateKey: launchActions.running ? "danger" : launchActions.pendingChanges && !launchActions.needsInstall ? "warning" : "primary"
        textKey: launchActions.running ? "common.close" : launchActions.needsInstall ? "builds.install" : launchActions.coreState.syncing ? "builds.syncing" : "builds.play"
        iconSource: IconSources[launchActions.running ? "stop" : launchActions.needsInstall ? "cores" : "play"] || ""
        mainEnabled: !launchActions.coreState.syncing
        secondaryEnabled: !launchActions.coreState.syncing
        actions: [
            {
                key: "play",
                text_key: "builds.play"
            },
            {
                key: "other",
                text_key: "builds.play_other",
                children: Session.accounts.map(account => ({
                            key: "account:" + account.id,
                            text: account.name
                        }))
            }
        ]
        onActivated: {
            if (launchActions.running)
                Session.command("close_client", launchActions.buildId)
            else
                launchActions.requestPlay()
        }
        onActionRequested: key => launchActions.requestLaunch(key === "play" ? "" : key.slice(8))
        Binding {
            target: split.secondary
            property: "visible"
            value: !launchActions.running && !launchActions.needsInstall
        }
        Binding {
            target: split.primary
            property: "rightRadius"
            value: split.secondary.visible ? split.innerRadius : split.appearance.radius
        }
        Binding {
            target: split.secondary
            property: "iconSource"
            value: IconSources["chevron-down"] || ""
        }
        Binding {
            target: split.secondary
            property: "displayText"
            value: ""
        }
        Binding {
            target: split.secondary
            property: "useDisplayText"
            value: true
        }
    }
    RowLayout {
        anchors.fill: parent
        visible: launchActions.installing
        spacing: Style.value((launchActions.Window.window ? launchActions.Window.window.appearance : null), "buildActionsSpacing")
        UG.ProgressButton {
            tag: "ui.build.installing"
            objectName: "build.progress." + launchActions.buildId
            Layout.fillWidth: true
            stateKey: "primary"
            displayText: Math.floor(launchActions.coreState.progress) + "%"
            progress: launchActions.coreState.progress / 100
            paused: !!launchActions.coreState.paused
            tooltip: launchActions.coreState.stage || ""
        }
        UG.ToolButton {
            tag: "ui.build.pause"
            Layout.preferredWidth: Style.value((launchActions.Window.window ? launchActions.Window.window.appearance : null), "buildActionsPreferredWidth")
            Layout.preferredHeight: Style.value((launchActions.Window.window ? launchActions.Window.window.appearance : null), "buildActionsPreferredHeight")
            stateKey: "secondary"
            displayText: ""
            useDisplayText: true
            iconSource: IconSources[launchActions.coreState.paused ? "play" : "pause"] || ""
            Accessible.name: Session.text(launchActions.coreState.paused ? "downloads.resume" : "downloads.pause")
            tooltipKey: launchActions.coreState.paused ? "downloads.resume" : "downloads.pause"
            onActivated: Session.command("pause_download", launchActions.coreState.core_id)
        }
        UG.ToolButton {
            tag: "ui.build.cancel"
            Layout.preferredWidth: Style.value((launchActions.Window.window ? launchActions.Window.window.appearance : null), "buildActionsPreferredWidth")
            Layout.preferredHeight: Style.value((launchActions.Window.window ? launchActions.Window.window.appearance : null), "buildActionsPreferredHeight")
            stateKey: "secondary"
            displayText: ""
            useDisplayText: true
            iconSource: IconSources["close"] || ""
            Accessible.name: Session.text("downloads.cancel")
            tooltipKey: "downloads.cancel"
            onActivated: Session.command("cancel_download", launchActions.coreState.core_id)
        }
    }
}
