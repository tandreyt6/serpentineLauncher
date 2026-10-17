import "Style.js" as Style
import QtQuick
import Working.Gui as UG

UG.Widget {
    id: indicator
    implicitWidth: Style.value(indicator.appearance, "loadingIndicatorImplicitWidth")
    implicitHeight: Style.value(indicator.appearance, "loadingIndicatorImplicitHeight")
    padding: 0
    background: null
    property color indicatorColor: appearance.accent
    Accessible.role: Accessible.ProgressBar
    Accessible.name: Session.text("versions.loading")
    contentItem: Item {
        Repeater {
            model: 12
            delegate: Item {
                required property int index
                anchors.fill: parent
                rotation: index * 30
                Rectangle {
                    width: Style.value(indicator.appearance, "loadingIndicatorWidth")
                    height: Style.value(indicator.appearance, "loadingIndicatorHeight")
                    radius: Style.value(indicator.appearance, "loadingIndicatorRadius")
                    x: (parent.width - width) / 2
                    y: 1
                    color: indicator.indicatorColor
                    opacity: Style.value(indicator.appearance, "loadingIndicatorOpacity") + index / Style.value(indicator.appearance, "loadingIndicatorOpacity2") * Style.value(indicator.appearance, "loadingIndicatorOpacity3")
                }
            }
        }
        RotationAnimator on rotation {
            from: 0
            to: 360
            duration: Style.value(indicator.appearance, "loadingIndicatorDuration")
            loops: Animation.Infinite
            running: !indicator.suspended && !indicator.reducedMotion
        }
    }
}
