import QtQuick
import Working.Gui as UG

Item {
    id: visual
    required property var viewState
    readonly property var s: viewState.style
    readonly property bool tabAction: typeof s.tabIconName === "string"
    readonly property string iconUrl: tabAction ? viewState.assetUrl("assets/" + s.tabIconName + ".png") : viewState.iconSource.toString()
    Rectangle {
        anchors.fill: parent
        topLeftRadius: viewState.leftRadius
        bottomLeftRadius: viewState.leftRadius
        topRightRadius: viewState.rightRadius
        bottomRightRadius: viewState.rightRadius
        color: visual.tabAction ? viewState.pressed ? s.tabActionPressed : viewState.hovered ? s.tabActionHover : s.tabActionBackground : !viewState.enabled ? s.disabled : viewState.pressed ? s.accentPressed : viewState.hovered ? s.accentHover : viewState.checked ? s.selection : s.buttonBackground
        border.width: viewState.focused ? s.focusWidth : 0
        border.color: s.focus
        Behavior on color {
            ColorAnimation {
                duration: viewState.reducedMotion || viewState.suspended ? 0 : s.duration
            }
        }
    }
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - 12)
        height: 2
        radius: 1
        color: s.accent
        visible: viewState.checked && !visual.tabAction
    }
    Row {
        anchors.centerIn: parent
        spacing: visual.iconUrl.length && !visual.tabAction && viewState.text.length ? s.iconGap : 0
        Item {
            width: visual.iconUrl.length ? s.iconSize : 0
            height: s.iconSize
            anchors.verticalCenter: parent.verticalCenter
            UG.Icon {
                anchors.fill: parent
                tag: "theme.button.icon"
                source: visual.iconUrl
                tint: !viewState.enabled ? s.disabledText : viewState.checked ? s.foreground : s.accentText
                fillMode: Image.PreserveAspectFit
            }
        }
        Text {
            width: Math.min(implicitWidth, Math.max(0, visual.width - 2 * s.controlPadding - (visual.iconUrl.length ? s.iconSize + s.iconGap : 0)))
            elide: Text.ElideRight
            text: visual.tabAction ? "" : viewState.text
            color: !viewState.enabled ? s.disabledText : viewState.checked ? s.foreground : s.accentText
            font.family: s.fontFamily
            font.pixelSize: s.fontSize
            font.weight: Font.DemiBold
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
