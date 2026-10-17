import "Launcher/Style.js" as Style
import QtQuick
import Qt5Compat.GraphicalEffects
import Working.Gui as UG

UG.AppWindow {
    id: window
    tag: "app.main"
    objectName: "launcher.main"
    readonly property var boot: typeof Boot !== "undefined" ? Boot : null
    readonly property bool startupComplete: !boot || boot.phase === "shown"
    readonly property alias mainContent: interfaceLoader.item
    readonly property bool bootSceneLoaded: bootLoader.status === Loader.Ready
    function loadMain() {
        interfaceLoader.setSource(ThemeUI.viewUrl("Main.qml"), {hostWindow: window})
    }
    Rectangle {
        id: startupViewport
        objectName: "launcher.startup.viewport"
        anchors.fill: parent
        color: window.appearance.background
        readonly property real bottomRadius: window.nativeFrame || window.nativeSnapped || window.visibility !== Window.Windowed ? 0 : Math.max(0, window.appearance.windowRadius - window.appearance.windowBorderWidth)
        readonly property bool roundedClipActive: Gui.hardwareAcceleration && !window.startupComplete && bottomRadius > 0
        topLeftRadius: 0
        topRightRadius: 0
        bottomLeftRadius: bottomRadius
        bottomRightRadius: bottomRadius
        clip: true


        layer.enabled: roundedClipActive
        layer.textureSize: Qt.size(Math.max(1, Math.ceil(width * Screen.devicePixelRatio)), Math.max(1, Math.ceil(height * Screen.devicePixelRatio)))
        layer.smooth: false
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: startupViewport.width
                height: startupViewport.height
                topLeftRadius: 0
                topRightRadius: 0
                bottomLeftRadius: startupViewport.bottomRadius
                bottomRightRadius: startupViewport.bottomRadius
            }
        }
        Loader {
            id: interfaceLoader
            objectName: "launcher.startup.loader"
            anchors.fill: parent
            asynchronous: true
            enabled: window.startupComplete
            onLoaded: {
                if (window.boot) {
                    Qt.callLater(function () {
                        if (interfaceLoader.item && typeof interfaceLoader.item.prepareStartup === "function")
                            interfaceLoader.item.prepareStartup()
                    })
                    window.boot.uiLoaded()
                }
            }
            onStatusChanged: if (status === Loader.Error) ThemeUI.mainFailed(UiDiagnostics["qml.main_failed"])
        }
        Loader {
            id: bootLoader
            objectName: "launcher.startup.bootLoader"
            anchors.fill: parent
            active: !!window.boot && !window.startupComplete
            onLoaded: if (window.boot) window.boot.bootLoaded()
            onStatusChanged: if (status === Loader.Error && window.boot) window.boot.bootFailed(UiDiagnostics["qml.boot_failed"])
        }
        Connections {
            target: window.boot
            function onReadyRequested() {
                if (!bootLoader.item || typeof bootLoader.item.showReady !== "function") {
                    window.boot.bootFailed(UiDiagnostics["qml.ready_missing"])
                    return
                }
                bootLoader.item.showReady()
            }
            function onSourceChanged() { Qt.callLater(function () { bootLoader.setSource(window.boot.source, {boot: window.boot}) }) }
        }
        Connections {
            target: typeof ThemeUI !== "undefined" ? ThemeUI : null
            function onMainSceneChanged() { window.loadMain() }
        }
        Text {
            anchors.centerIn: parent
            width: Math.min(parent.width - Style.value(window.appearance, "windowWidth"), Style.value(window.appearance, "windowWidth2"))
            visible: !!window.boot && window.boot.phase === "failed"
            text: window.boot ? window.boot.error : ""
            color: window.appearance.foreground
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            z: 10
        }
    }
    Component.onCompleted: {
        if (boot) bootLoader.setSource(boot.source, {boot: boot})
        else loadMain()
    }
}
