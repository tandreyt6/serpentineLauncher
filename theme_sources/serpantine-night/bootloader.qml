import QtQuick
import QtQuick.Shapes


Rectangle {
    id: screen
    required property var boot
    objectName: "launcher.startup.screen"
    color: boot.style.background

    readonly property var hostWindow: Window.window
    readonly property real bottomRadius: !hostWindow || hostWindow.nativeFrame || hostWindow.nativeSnapped || hostWindow.visibility !== Window.Windowed ? 0 : Math.max(0, boot.style.windowRadius - boot.style.windowBorderWidth)
    topLeftRadius: 0
    topRightRadius: 0
    bottomLeftRadius: bottomRadius
    bottomRightRadius: bottomRadius
    property bool ready: false
    property real introduction: 0
    function showReady() {
        if (ready) return
        ready = true
        completion.start()
    }
    Column {
        anchors.centerIn: parent
        width: Math.min(620, parent.width - 48)
        spacing: 26
        opacity: screen.introduction
        transform: Translate { y: (1 - screen.introduction) * 12 }
        Item {
            width: 44
            height: 44
            anchors.horizontalCenter: parent.horizontalCenter
            Item {
                id: spinner
                objectName: "launcher.startup.spinner"
                anchors.fill: parent
                Rectangle {
                    anchors.centerIn: parent
                    width: 36
                    height: 36
                    radius: 18
                    color: "transparent"
                    border.width: 3
                    border.color: screen.boot.style.accent
                    opacity: 0.12
                    antialiasing: true
                }
                Shape {
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeWidth: 3
                        strokeColor: screen.boot.style.accent
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathAngleArc {
                            centerX: 22
                            centerY: 22
                            radiusX: 18
                            radiusY: 18
                            startAngle: -90
                            sweepAngle: 260
                        }
                    }
                }
                RotationAnimation on rotation {
                    from: 0
                    to: 360
                    duration: 1050
                    easing.type: Easing.Linear
                    loops: Animation.Infinite
                    running: screen.visible
                }
            }
        }
        Item {
            width: parent.width
            height: Math.max(preparing.implicitHeight, completed.implicitHeight)
            Text {
                id: preparing
                objectName: "launcher.startup.preparing"
                anchors.fill: parent
                text: screen.boot.preparingText
                font.family: screen.boot.style.fontFamily
                font.pixelSize: 20
                color: screen.boot.style.foreground
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                opacity: screen.ready ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.InOutCubic } }
            }
            Text {
                id: completed
                objectName: "launcher.startup.ready"
                anchors.fill: parent
                text: screen.boot.readyText
                font.family: screen.boot.style.fontFamily
                font.pixelSize: 20
                color: screen.boot.style.foreground
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                opacity: screen.ready ? 1 : 0
                transform: Translate {
                    y: screen.ready ? 0 : 7
                    Behavior on y { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
                }
                Behavior on opacity { NumberAnimation { duration: 280; easing.type: Easing.InOutCubic } }
            }
        }
    }
    NumberAnimation on introduction { from: 0; to: 1; duration: 520; easing.type: Easing.OutCubic }
    SequentialAnimation {
        id: completion
        PauseAnimation { duration: 250 }
        ScriptAction { script: screen.boot.reveal() }
        NumberAnimation { target: screen; property: "opacity"; to: 0; duration: 420; easing.type: Easing.InOutCubic }
        ScriptAction { script: screen.boot.finish() }
    }
}
