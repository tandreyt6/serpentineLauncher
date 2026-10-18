import QtQuick
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
    property url errorIconSource: IconSources["theme-error"]
    property color errorIconTint: appearance.danger
    Accessible.name: { Session.locale; return Session.text("downloads.stopped") }
    Accessible.description: tooltip
    readonly property bool errorTooltipVisible: QC.ToolTip.toolTip.visible && QC.ToolTip.toolTip.parent === indicator && QC.ToolTip.toolTip.text === tooltip
    contentItem: UG.Icon {
        tag: indicator.tag + ".icon"
        source: indicator.errorIconSource
        tint: indicator.errorIconTint
        fillMode: Image.PreserveAspectFit
    }
}
