import QtQuick
import QtQuick.Shapes
import QtQuick.Controls as QC
import Working.Gui as UG

UG.Widget {
    id: indicator
    tag: "ui.task.error"
    objectName: "task.error.indicator"
    textFromTag: false
    displayText: ""
    useDisplayText: true
    background: null
    padding: 0
    implicitWidth: appearance.iconSize
    implicitHeight: implicitWidth
    property url errorIconSource
    property color errorIconTint: appearance.danger
    Accessible.name: Session.text("downloads.stopped")
    Accessible.description: tooltip
    readonly property bool errorTooltipVisible: QC.ToolTip.toolTip.visible && QC.ToolTip.toolTip.parent === indicator && QC.ToolTip.toolTip.text === tooltip
    contentItem: Item {
        UG.Icon {
            tag: indicator.tag + ".icon"
            anchors.fill: parent
            source: indicator.errorIconSource
            tint: indicator.errorIconTint
            fillMode: Image.PreserveAspectFit
            visible: source.toString().length > 0
        }
        Shape {
            anchors.fill: parent
            visible: !indicator.errorIconSource.toString().length
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeWidth: 0
                fillColor: indicator.appearance.danger
                startX: indicator.availableWidth / 2
                startY: 0
                PathLine {
                    x: indicator.availableWidth
                    y: indicator.availableHeight
                }
                PathLine {
                    x: 0
                    y: indicator.availableHeight
                }
                PathLine {
                    x: indicator.availableWidth / 2
                    y: 0
                }
            }
        }
        Text {
            visible: !indicator.errorIconSource.toString().length
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            text: "!"
            color: indicator.appearance.dangerText
            font.family: indicator.appearance.fontFamily
            font.pixelSize: indicator.appearance.fontSize
            font.weight: Font.Bold
        }
    }
}
