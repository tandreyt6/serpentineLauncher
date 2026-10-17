import "../Launcher/Style.js" as Style
import "../Launcher/QuickSearch.js" as Search
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import Working.Gui as UG
import Launcher

UG.PopupPanel {
    id: dialog
    tag: "ui.quickSwitch"
    objectName: "quickSwitch.dialog"
    parent: QC.Overlay.overlay
    modal: true
    focus: true
    property string filterKind: "all"
    property string pendingLaunch: ""
    property string selectedResult: ""
    readonly property string buildSignature: visible ? JSON.stringify(Session.builds.map(build => ({id: build.id, title: build.title, minecraft: build.minecraft, loader: build.loader, running: build.running}))) : ""
    readonly property var entries: {
        if (!visible)
            return []
        Session.locale
        const builds = []
        JSON.parse(buildSignature).forEach(build => builds.push({
            key: build.id,
            title: build.title,
            detail: Session.text("quick.build") + " · " + build.minecraft + " · " + build.loader,
            icon: "builds",
            action: "edit",
            running: build.running
        }, {
            key: build.id,
            title: build.title,
            detail: Session.text(build.running ? "quick.running" : "quick.launch") + " · " + build.minecraft + " · " + build.loader,
            icon: "play",
            action: "launch",
            running: build.running
        }))
        const pages = ["builds", "profile", "cores", "styles", "settings"]
        return builds.concat(pages.map(key => ({
            key: key,
            title: Session.text("nav." + key),
            detail: Session.text("quick.page"),
            icon: key,
            action: "navigate",
            running: false
        })))
    }
    readonly property var results: visible ? Search.find(entries.filter(entry => filterKind === "all" || entry.action === filterKind), query.text) : []
    readonly property real rowHeight: Style.value(appearance, "quickSwitchRowHeight")
    readonly property real rowGap: Style.value(appearance, "quickSwitchRowGap")
    width: Math.max(0, Math.min(Style.value(appearance, "quickSwitchWidth"), parent ? parent.width - 2 * appearance.pageMargin : 0))
    height: Math.max(0, Math.min(parent ? parent.height - 2 * appearance.pageMargin : 0,
        topPadding + bottomPadding + heading.implicitHeight + query.implicitHeight + categories.implicitHeight + hints.implicitHeight + 4 * body.spacing
        + Math.max(rowHeight, Math.min(results.length, Style.value(appearance, "quickSwitchVisibleRows")) * (rowHeight + rowGap) - rowGap)))
    x: parent ? (parent.width - width) / 2 : 0
    y: parent ? Math.max(appearance.pageMargin, (parent.height - height) * Style.value(appearance, "quickSwitchVerticalPosition")) : 0
    onResultsChanged: {
        const previous = results.findIndex(entry => entry.action + ":" + entry.key === selectedResult)
        resultsList.currentIndex = previous >= 0 ? previous : results.length ? 0 : -1
        rememberSelection()
        Qt.callLater(keepSelectionVisible)
    }
    onFilterKindChanged: resetSelection()
    function rememberSelection() {
        const entry = results[resultsList.currentIndex]
        selectedResult = entry ? entry.action + ":" + entry.key : ""
    }
    function keepSelectionVisible() {
        if (visible && resultsList.currentIndex >= 0)
            resultsList.positionViewAtIndex(resultsList.currentIndex, ListView.Contain)
    }
    function resetSelection() {
        resultsList.currentIndex = results.length ? 0 : -1
        rememberSelection()
    }
    onAboutToShow: {
        filterKind = "all"
        query.clear()
        resetSelection()
    }
    onOpened: query.forceActiveFocus()
    onClosed: {
        if (pendingLaunch.length) {
            launch.buildId = pendingLaunch
            pendingLaunch = ""
            launch.requestPlay()
        }
    }
    LaunchRequest {
        id: launch
        parent: dialog.parent && dialog.parent.Window.window ? dialog.parent.Window.window.contentItem : null
        visible: false
        launchOrigin: Window.window && Window.window.objectName.startsWith("launcher.editor.") ? "editor" : "launcher"
    }
    ShortcutHost {
        parent: query
        contextKey: "palette"
        popupScope: true
        enabled: dialog.opened && dialog.activeFocus
        onTriggered: action => {
            if (action === "quickLaunch")
                dialog.launchSelected()
        }
    }
    function launchSelected() {
        const entry = results[resultsList.currentIndex]
        if (entry && entry.action !== "navigate" && !entry.running) {
            pendingLaunch = entry.key
            close()
        }
    }
    function acceptQuery(event) {
        if (!(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier | Qt.MetaModifier)))
            activate(resultsList.currentIndex)
        event.accepted = true
    }
    function moveSelection(delta) {
        if (!results.length)
            return
        resultsList.currentIndex = (resultsList.currentIndex + delta + results.length) % results.length
        rememberSelection()
        resultsList.positionViewAtIndex(resultsList.currentIndex, ListView.Contain)
    }
    function activate(index) {
        if (index < 0 || index >= results.length)
            return
        const entry = results[index]
        if (entry.action === "launch") {
            launchSelected()
            return
        }
        close()
        Session.command(entry.action, entry.key)
    }
    contentItem: ColumnLayout {
        id: body
        spacing: dialog.appearance.spacing
        RowLayout {
            id: heading
            Layout.fillWidth: true
            UG.UiText {
                tag: "ui.quickSwitch.heading"
                textKey: "quick.heading"
                typographyRole: "heading"
                Layout.fillWidth: true
            }
            UG.UiText {
                tag: "ui.quickSwitch.shortcut"
                displayText: Session.shortcutLabel(Session.settings["shortcut.quickSwitch"])
                useDisplayText: true
                typographyRole: "caption"
            }
        }
        RowLayout {
            id: categories
            Layout.fillWidth: true
            spacing: dialog.appearance.smallGap
            Repeater {
                model: ["all", "edit", "launch", "navigate"]
                delegate: UG.Button {
                    required property string modelData
                    tag: "ui.quickSwitch.category"
                    objectName: "quickSwitch.category." + modelData
                    textKey: "quick.category." + modelData
                    stateKey: dialog.filterKind === modelData ? "primary" : "secondary"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    focusPolicy: Qt.NoFocus
                    onActivated: { dialog.filterKind = modelData; query.forceActiveFocus() }
                }
            }
        }
        UG.TextField {
            id: query
            objectName: "quickSwitch.query"
            tag: "ui.quickSwitch.query"
            textKey: "quick.placeholder"
            onTextChanged: dialog.resetSelection()
            iconSource: IconSources["search"]
            Layout.fillWidth: true
            Keys.onDownPressed: event => { dialog.moveSelection(1); event.accepted = true }
            Keys.onUpPressed: event => { dialog.moveSelection(-1); event.accepted = true }
            Keys.onReturnPressed: event => dialog.acceptQuery(event)
            Keys.onEnterPressed: event => dialog.acceptQuery(event)
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            ListView {
                id: resultsList
                objectName: "quickSwitch.results"
                anchors.fill: parent
                clip: true
                spacing: dialog.rowGap
                model: dialog.results
                boundsBehavior: Flickable.StopAtBounds
                keyNavigationEnabled: false
                QC.ScrollBar.vertical: QC.ScrollBar {}
                delegate: UG.Button {
                    id: result
                    required property int index
                    required property var modelData
                    tag: "ui.quickSwitch.result"
                    objectName: "quickSwitch.result." + index
                    width: resultsList.width
                    height: dialog.rowHeight
                    focusPolicy: Qt.NoFocus
                    enabled: modelData.action !== "launch" || !modelData.running
                    stateKey: resultsList.currentIndex === index ? "selected" : "secondary"
                    displayText: modelData.title
                    useDisplayText: true
                    hideText: true
                    onActivated: dialog.activate(index)
                    contentItem: RowLayout {
                        spacing: result.appearance.iconGap
                        UG.Icon {
                            tag: "ui.quickSwitch.result.icon"
                            source: IconSources[result.modelData.icon]
                            tint: resultsList.currentIndex === result.index ? result.appearance.accent : result.appearance.foreground
                            Layout.preferredWidth: result.appearance.iconSize
                            Layout.preferredHeight: result.appearance.iconSize
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            UG.UiText {
                                tag: "ui.quickSwitch.result.title"
                                displayText: result.modelData.title
                                useDisplayText: true
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            UG.UiText {
                                tag: "ui.quickSwitch.result.detail"
                                displayText: result.modelData.detail
                                useDisplayText: true
                                typographyRole: "caption"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        Rectangle {
                            visible: result.modelData.running
                            color: result.appearance.accent
                            radius: width / 2
                            Layout.preferredWidth: Style.value(dialog.appearance, "quickSwitchStatusSize")
                            Layout.preferredHeight: width
                        }
                        UG.Icon {
                            tag: "ui.quickSwitch.result.arrow"
                            source: IconSources["back"]
                            rotation: 180
                            tint: result.appearance.muted
                            Layout.preferredWidth: result.appearance.iconSize
                            Layout.preferredHeight: result.appearance.iconSize
                        }
                    }
                }
            }
            UG.UiText {
                tag: "ui.quickSwitch.empty"
                textKey: "quick.empty"
                visible: !dialog.results.length
                anchors.centerIn: parent
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }
        UG.UiText {
            id: hints
            tag: "ui.quickSwitch.hints"
            displayText: {
                Session.settings
                Session.locale
                const sequence = Session.shortcutLabel(Session.settings["shortcut.quickLaunch"])
                return Session.formatText("quick.hints", {launch: sequence.length ? Session.formatText("quick.launch_hint", {shortcut: sequence}) : "", action: Session.text(dialog.results[resultsList.currentIndex] && dialog.results[resultsList.currentIndex].action === "launch" ? "quick.enter_launch" : "quick.enter_open")})
            }
            useDisplayText: true
            typographyRole: "caption"
            Layout.fillWidth: true
            elide: Text.ElideRight
        }
    }
}
