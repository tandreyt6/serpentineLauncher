import "Launcher/Style.js" as Style
import "Launcher/ShortcutTargets.js" as Targets
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import Qt5Compat.GraphicalEffects
import Working.Gui as UG
import Launcher
import "pages" as Pages

Item {
    id: window
    required property var hostWindow
    readonly property var appearance: hostWindow.appearance
    readonly property bool nativeFrame: hostWindow.nativeFrame
    readonly property bool nativeSnapped: hostWindow.nativeSnapped
    readonly property int visibility: hostWindow.visibility
    objectName: "launcher.main"
    ToolTipPolicy {}
    readonly property bool inSettings: Session.currentPage === "settings" || Session.currentPage === "buildAbout"
    readonly property bool rightPanel: navigation.placement === "right"
    readonly property bool navigationConfiguring: navigationSettings.openingRequested || navigationSettings.popupVisible
    property bool startupPrepared: !hostWindow.boot
    property var startupPages: []
    readonly property bool startupReady: !!centralStack.item && centralStack.item.status === Loader.Ready
        && startupPrepared && startupPages.every(page => page && page.status === Loader.Ready)
    function prepareStartup() {
        if (startupPrepared)
            return
        startupPages = centralStack.pages.filter(page => page.key !== "buildAbout" && page.key !== centralStack.currentKey)
            .map(page => centralStack.preparePage(page.key))
        startupPrepared = true
    }
    readonly property bool firstRunUiReady: startupReady && enabled && hostWindow.startupComplete
    onFirstRunUiReadyChanged: if (firstRunUiReady) Qt.callLater(prepareFirstRun)
    Component.onCompleted: {
        Qt.callLater(prepareFirstRun)
    }
    function prepareFirstRun() {
        if (!firstRunUiReady)
            return
        Session.prepareFirstRun()
        if (Session.firstRunPending && !firstRunReminder.popupVisible && !firstRunReminder.openingRequested)
            firstRunReminder.open()
    }
    Connections {
        target: Session
        function onFirstRunChanged() { window.prepareFirstRun() }
        function onChanged() { window.prepareFirstRun() }
    }
    readonly property real reservedWidth: inSettings || navigation.horizontal ? 0 : navigation.reservedWidth * (1 - navigation.edgeHiddenProgress)
    property bool hudHidden: false
    property bool navigationWasOpened: false
    property bool navigationSetupPending: false
    function toggleHud() {
        navigationMenu.close()
        activity.close()
        quickSwitch.close()
        hudHidden = !hudHidden
    }
    UG.ToolButton {
        id: hudToggle
        parent: window.hostWindow.contentItem
        objectName: "hud.toggle"
        visible: window.hostWindow.startupComplete
        tag: "ui.hud.toggle"
        z: 2000000
        x: (window.nativeFrame ? 0 : window.hostWindow.frameInset + window.appearance.windowBorderWidth) + window.appearance.pageMargin
        y: window.hostWindow.alignToPixel(window.nativeFrame ? 0 : window.hostWindow.frameInset + (window.visibility === Window.FullScreen ? 0 : window.appearance.titlebarHeight)) + (window.appearance.headerHeight - height) / 2
        width: window.appearance.controlHeight
        height: width
        hideText: true
        textFromTag: false
        displayText: ""
        useDisplayText: true
        iconSource: IconSources["eye"]
        checked: window.hudHidden
        tooltip: { Session.locale; return Session.text(window.hudHidden ? "hud.show" : "hud.hide") }
        Accessible.name: tooltip
        onActivated: window.toggleHud()
    }
    Binding {
        target: QC.Overlay.overlay
        property: "opacity"
        value: 0
        when: window.hudHidden
        restoreMode: Binding.RestoreBindingOrValue
    }
    Binding {
        target: QC.Overlay.overlay
        property: "enabled"
        value: false
        when: window.hudHidden
        restoreMode: Binding.RestoreBindingOrValue
    }
    function openQuickSwitch() {
        if (navigationConfiguring || navigationSetupPending || !enabled)
            return
        navigationMenu.close()
        activity.close()
        quickSwitch.open()
    }
    ShortcutHost {
        contextKey: "main"
        enabled: window.enabled && !window.hudHidden && !window.navigationConfiguring && !window.navigationSetupPending
        onTriggered: action => {
            if (action === "quickSwitch")
                window.openQuickSwitch()
            else if (action === "settings")
                Session.command("navigate", "settings")
            else if (action === "tasks")
                activity.open()
            else if (action === "back" && window.inSettings)
                Session.command("back", "")
            else if (action === "launchBuild" && Session.currentPage === "builds")
                keyboardLaunch.requestPlay()
            else if (action === "stopBuild" && Session.currentPage === "builds")
                keyboardLaunch.requestStop()
            else if (action === "editBuild" && Session.currentPage === "builds" && Session.selectedId.length)
                Session.command("edit", Session.selectedId)
            else if (action === "openFolder" && Session.currentPage === "builds" && Session.selectedId.length)
                Session.command("open_build_folder", Session.selectedId)
            else if (action === "createBuild") {
                if (Session.currentPage !== "builds")
                    Session.command("navigate", "builds")
                createShortcut.open()
            } else
                Targets.dispatch(centralStack.item, action)
        }
    }
    LaunchRequest {
        id: keyboardLaunch
        visible: false
        buildId: Session.selectedId
    }
    function openNavigationSettings() {
        if (navigationConfiguring || navigationSetupPending)
            return
        navigationSetupPending = true
        navigationMenu.close()
        activity.close()
        if (inSettings)
            Session.command("back", "")
        Qt.callLater(function () {
            if (window.inSettings)
                Session.command("navigate", "builds")
            window.navigationWasOpened = navigation.opened
            navigationSettings.open()
            window.navigationSetupPending = false
        })
    }

    Rectangle {
        id: shell
        objectName: "launcher.shell"
        anchors.fill: parent
        color: window.appearance.background
        readonly property real bottomRadius: window.nativeFrame || window.nativeSnapped || window.visibility !== Window.Windowed ? 0 : Math.max(0, window.appearance.windowRadius - window.appearance.windowBorderWidth)
        topLeftRadius: 0
        topRightRadius: 0
        bottomLeftRadius: bottomRadius
        bottomRightRadius: bottomRadius
        clip: true
        layer.enabled: Gui.hardwareAcceleration && bottomRadius > 0
        layer.textureSize: Qt.size(Math.max(1, Math.ceil(width * Screen.devicePixelRatio)), Math.max(1, Math.ceil(height * Screen.devicePixelRatio)))
        layer.smooth: false
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: shell.width
                height: shell.height
                topLeftRadius: 0
                topRightRadius: 0
                bottomLeftRadius: shell.bottomRadius
                bottomRightRadius: shell.bottomRadius
            }
        }
        ThemeBackground {
            tag: "ui.background.main"
            objectName: "theme.background.main"
            anchors.fill: parent
        }
        Item {
            id: hud
            objectName: "launcher.hud"
            anchors.fill: parent
            visible: !window.hudHidden
            enabled: visible
            Item {
                id: header
                objectName: "launcher.header"
                enabled: !window.navigationConfiguring
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: window.appearance.headerHeight
                Row {
                    id: accountControls
                    objectName: "account.controls"
                    anchors.right: parent.right
                    anchors.rightMargin: window.appearance.pageMargin
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Style.value(window.appearance, "mainSpacing")
                    UG.ToolButton {
                        tag: "ui.quickSwitch.open"
                        objectName: "quickSwitch.open"
                        width: height
                        height: window.appearance.controlHeight
                        iconSource: IconSources["search"]
                        displayText: ""
                        useDisplayText: true
                        tooltip: {
                            Session.settings
                            Session.locale
                            const shortcut = Session.shortcutLabel(Session.settings["shortcut.quickSwitch"])
                            return shortcut.length ? Session.formatText("quick.open", {shortcut: shortcut}) : Session.text("shortcuts.action.quickSwitch")
                        }
                        Accessible.name: Session.text("shortcuts.action.quickSwitch")
                        onActivated: window.openQuickSwitch()
                    }
                    UG.UiText {
                        tag: "ui.main.1"
                        verticalAlignment: Text.AlignVCenter
                        height: window.appearance.controlHeight
                        textKey: "common.offline"
                        typographyRole: (true) ? "caption" : "body"
                        font.pixelSize: Style.value(window.appearance, "mainPixelSize")
                    }
                    UG.ComboBox {
                        id: selection0
                        density: "compact"
                        tag: "ui.main.2"
                        valueRole: "key"
                        textRole: "text"
                        secondaryRole: "secondary"

                        objectName: "account.button"
                        width: Math.min(Style.value(window.appearance, "mainWidth"), Math.max(Style.value(window.appearance, "mainWidth2"), accountMetrics.advanceWidth + Style.value(window.appearance, "mainWidth3")))
                        searchable: true
                        model: {
                            const options = (function () {
                                    return Session.accounts.map(account => ({
                                                value: account.id,
                                                label: account.name
                                            }))
                                })()
                            return options.map(option => ({
                                        key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                        text: option.label === undefined ? option.text : option.label,
                                        secondary: option.note || option.secondary || "",
                                        pinned: !!option.pinned,
                                        enabled: option.enabled !== false
                                    }))
                        }
                        selectedKey: Session.activeAccountId || "__all__"

                        onSelectionRequested: selected => {
                            const value = selected === "__all__" ? "" : selected
                            Session.command("account", value)
                        }
                        TextMetrics {
                            id: accountMetrics
                            text: Session.activeAccount
                            font.family: window.appearance.fontFamily
                            font.pixelSize: window.appearance.fontSize
                        }
                    }
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: window.appearance.border
                }
            }
            Item {
                id: pages
                enabled: !window.navigationConfiguring
                anchors.top: header.bottom
                anchors.bottom: footer.top
                anchors.left: parent.left
                anchors.right: parent.right

                anchors.leftMargin: window.rightPanel ? 0 : window.reservedWidth
                anchors.rightMargin: window.rightPanel ? window.reservedWidth : 0

                UG.AnimatedStack {
                    id: centralStack
                    tag: "ui.pages"
                    objectName: "launcher.pages"
                    anchors.fill: parent
                    retentionPolicy: "keep"
                    maximumRetained: 5
                    currentKey: Session.currentPage
                    pages: [
                        {
                            key: "builds",
                            component: buildsPage
                        },
                        {
                            key: "profile",
                            component: profilePage
                        },
                        {
                            key: "cores",
                            component: coresPage
                        },
                        {
                            key: "styles",
                            component: stylesPage
                        },
                        {
                            key: "settings",
                            component: settingsPage
                        },
                        {
                            key: "buildAbout",
                            component: aboutPage
                        }
                    ]
                    Component {
                        id: buildsPage
                        LazyPage { viewKey: "pages/BuildsPage.qml" }
                    }
                    Component {
                        id: profilePage
                        LazyPage { viewKey: "pages/ProfilePage.qml" }
                    }
                    Component {
                        id: coresPage
                        LazyPage { viewKey: "pages/CoresPage.qml" }
                    }
                    Component {
                        id: stylesPage
                        LazyPage { viewKey: "pages/StylesPage.qml" }
                    }
                    Component {
                        id: settingsPage
                        LazyPage {
                            id: settingsPageLoader
                            viewKey: "pages/SettingsPage.qml"
                            Connections {
                                target: settingsPageLoader.item
                                function onNavigationSettingsRequested() { window.openNavigationSettings() }
                            }
                        }
                    }
                    Component {
                        id: aboutPage
                        LazyPage { viewKey: "pages/BuildAboutPage.qml" }
                    }
                }
            }
            Navigation {
                id: navigation
                objectName: "navigation.panel"
                visible: !window.inSettings
                actionsEnabled: !window.navigationConfiguring
                animateConfiguration: window.navigationConfiguring
                hoverCloseDelay: Number(Session.settings.panelHoverCloseMs)
                readonly property real horizontalLeft: placement === "bottom" ? versionInfo.x + versionInfo.width + window.appearance.pageMargin : window.appearance.pageMargin + hudToggle.width + window.appearance.iconGap
                readonly property real horizontalRight: placement === "bottom" ? tasksButton.x - window.appearance.pageMargin : accountControls.x - window.appearance.pageMargin
                width: horizontal ? Math.min(horizontalContentWidth, Math.max(0, horizontalRight - horizontalLeft)) : implicitWidth
                height: horizontal ? placement === "bottom" ? footer.height : header.height : Math.max(0, footer.y - header.height)
                x: horizontal ? horizontalLeft : window.rightPanel ? parent.width - width : 0
                y: placement === "top" ? header.y : placement === "bottom" ? footer.y : header.height
                z: 10
                model: ["builds", "profile", "cores", "styles", "settings"].map(key => ({
                            key: key,
                            text_key: "nav." + key,
                            icon: key
                        }))
                selectedKey: Session.currentPage
                requestedPlacement: Session.settings.panelSide
                horizontalLabels: Session.settings.panelLabels
                layoutMode: Session.settings.panelLayout
                alignment: Session.settings.panelAlign
                revealMode: horizontal ? "always-open" : ({
                        hover: "hover",
                        button: "button",
                        both: "hover+button",
                        open: "always-open",
                        closed: "always-closed"
                    })[Session.settings.panelMode]
                onPageRequested: key => {
                    if (!window.navigationConfiguring)
                        Session.command("navigate", key)
                }
                onContextRequested: (owner, x, y) => navigationMenu.popupAt(owner, x, y, "navigation")
            }
            Rectangle {
                objectName: "navigation.settings.scrim"
                anchors.fill: parent
                z: 5
                visible: window.navigationConfiguring
                enabled: false
                color: navigationSettings.item ? navigationSettings.item.appearance.overlayColor : window.appearance.overlayColor
            }
            Item {
                id: footer
                objectName: "launcher.footer"
                enabled: !window.navigationConfiguring
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: window.appearance.footerHeight
                Rectangle {
                    width: parent.width
                    height: 1
                    color: window.appearance.border
                }
                Row {
                    id: versionInfo
                    objectName: "launcher.version"
                    anchors.left: parent.left
                    anchors.leftMargin: Style.value(window.appearance, "mainLeftMargin")
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Style.value(window.appearance, "mainSpacing2")
                    UG.UiText {
                        tag: "ui.main.3"
                        verticalAlignment: Text.AlignVCenter
                        displayText: Session.version
                        typographyRole: (true) ? "caption" : "body"
                        font.pixelSize: Style.value(window.appearance, "mainPixelSize2")
                    }
                }
                UG.ProgressButton {
                    id: tasksButton
                    tag: "ui.tasks.button"
                    objectName: "activity.button"
                    stateKey: task && task.state === "failed" ? "danger" : "secondary"
                    readonly property var task: Session.settings.tasksDisplay === "latest" ? Session.downloads[Session.downloads.length - 1] || null : Session.downloads.find(download => !["failed", "completed", "cancelled"].includes(download.state) && !download.paused) || Session.downloads.find(download => !["failed", "completed", "cancelled"].includes(download.state)) || Session.downloads[Session.downloads.length - 1] || null
                    property string displayedTaskId: ""
                    onTaskChanged: {
                        const key = task ? task.id : ""
                        if (key !== displayedTaskId && key.length && Session.settings.tasksAutoOpen && !window.navigationConfiguring)
                            activity.open()
                        displayedTaskId = key
                    }
                    width: window.appearance.tasksWidth
                    anchors.right: parent.right
                    anchors.rightMargin: Style.value(window.appearance, "mainRightMargin")
                    anchors.verticalCenter: parent.verticalCenter
                    textFromTag: false
                    displayText: {
                        Session.locale
                        return task ? task.title + " · " + (["failed", "completed", "cancelled", "retrying"].includes(task.state) ? task.stage : Session.formatDownloadSpeed(task.bytes_per_second)) : Session.text("activity.open")
                    }
                    useDisplayText: true
                    showProgress: task !== null && !["failed", "completed", "cancelled"].includes(task.state)
                    progress: task ? task.progress / 100 : 0
                    paused: task ? task.paused : false
                    tooltip: task ? task.error || task.stage : ""
                    onActivated: activity.visible ? activity.close() : activity.open()
                }
            }
            UG.Notification {
                id: toast
                tag: "ui.notice"
                textFromTag: false
                objectName: "launcher.notice"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: footer.top
                anchors.bottomMargin: Style.value(window.appearance, "mainBottomMargin")
                width: Math.min(parent.width - Style.value(window.appearance, "mainWidth4"), Style.value(window.appearance, "mainWidth5"))
                z: 40
            }
            Connections {
                target: Session
                function onNotice(text) {
                    toast.message = text
                    toast.open()
                }
            }
            Pages.ActivityPopup {
                id: activity
                width: tasksButton.width
                x: parent.width - width - 16
                y: Math.max(0, parent.height - height - footer.height - 6)
            }
        }
    }
    ContextMenu {
        id: navigationMenu
        tag: "ui.navigation.context"
        objectName: "navigation.context"
        width: Style.value(window.appearance, "mainWidth6")
        height: appearance.controlHeight + topPadding + bottomPadding
        model: [
            {
                key: "settings",
                text_key: "settings.heading"
            }
        ]
        onTriggered: key => {
            if (key === "settings")
                window.openNavigationSettings()
        }
    }
    DeferredPopup {
        id: createShortcut
        source: ThemeUI.viewUrl("dialogs/CreateBuildDialog.qml")
    }
    DeferredPopup {
        id: quickSwitch
        objectName: "quickSwitch.loader"
        source: ThemeUI.viewUrl("dialogs/QuickSwitchDialog.qml")
    }
    DeferredPopup {
        id: navigationSettings
        objectName: "navigation.settings.loader"
        source: ThemeUI.viewUrl("dialogs/NavigationSettingsDialog.qml")
        Binding {
            target: navigationSettings.item
            property: "previewPanelWidth"
            value: navigation.appearance.navigationExpandedWidth
            when: navigationSettings.popupReady
        }
        Binding {
            target: navigationSettings.item
            property: "panelOpened"
            value: navigation.opened
            when: navigationSettings.popupReady
        }
        Connections {
            target: navigationSettings.item
            function onPreviewToggleRequested() { navigation.opened = !navigation.opened }
            function onClosed() { navigation.opened = window.navigationWasOpened }
        }
    }
    Connections {
        target: ThemeUI
        function onRetryRequested(theme, reason) {
            themeRetry.heading = Session.text("theme.retry_heading") + " · " + theme
            themeRetry.message = Session.text("theme.retry_warning") + "\n\n" + reason
            themeRetry.open()
        }
    }
    DeferredPopup {
        id: firstRunReminder
        objectName: "firstRun.reminder.loader"
        source: ThemeUI.viewUrl("dialogs/FirstRunDialog.qml")
    }
    DeferredPopup {
        id: updateDialog
        objectName: "updates.dialog.loader"
        source: ThemeUI.viewUrl("dialogs/UpdateDialog.qml")
    }
    Connections {
        target: Updates
        function onDialogRequested() { updateDialog.open() }
    }
    UG.ConfirmationDialog {
        id: themeRetry
        tag: "ui.theme.retry"
        objectName: "theme.retry.confirm"
        actions: [
            {
                key: "cancel",
                text_key: "common.cancel"
            },
            {
                key: "retry",
                text_key: "theme.retry",
                state_key: "danger"
            }
        ]
        cancelAction: "cancel"
        defaultAction: "cancel"
        onActionRequested: key => ThemeUI.resolveThemeRetry(key === "retry")
        onCancelled: ThemeUI.resolveThemeRetry(false)
    }
    Connections {
        target: Lifecycle
        function onQuitRequested() {
            quitDialog.open()
        }
    }
    UG.ConfirmationDialog {
        id: quitDialog
        tag: "ui.quit.confirm"
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
        cancelAction: "cancel"
        defaultAction: "save"
        onActionRequested: key => Lifecycle.resolveExit(key)
    }
}
