import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

UG.Button {
    id: button
    required property string buildId
    property string directory: ""
    tag: "ui.editor.folder"
    stateKey: "secondary"
    textKey: "editor.open_build_folder"
    iconSource: IconSources["folder-open"] || ""
    implicitWidth: Math.max(appearance.controlWidth, Math.ceil(metrics.advanceWidth) + leftPadding + rightPadding + appearance.iconSize + appearance.iconGap)
    Layout.minimumWidth: implicitWidth
    enabled: buildId.length > 0
    TextMetrics {
        id: metrics
        text: button.text
        font.family: button.appearance.fontFamily
        font.pixelSize: button.appearance.fontSize
        font.weight: Font.DemiBold
    }
    onActivated: Session.command("open_build_folder", buildId, directory)
}
