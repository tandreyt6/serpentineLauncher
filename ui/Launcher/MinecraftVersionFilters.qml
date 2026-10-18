import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

ColumnLayout {
    id: filters
    required property string tag
    property string titleRole: "caption"
    property bool showHint: false
    spacing: heading.appearance.smallGap
    UG.UiText {
        id: heading
        tag: filters.tag + ".heading"
        textKey: "minecraft.version_types"
        typographyRole: filters.titleRole
        Layout.fillWidth: true
    }
    Flow {
        Layout.fillWidth: true
        spacing: heading.appearance.smallGap
        Repeater {
            model: Session.minecraftVersionFilterChoices
            UG.CheckBox {
                required property var modelData
                tag: filters.tag + "." + modelData.type
                objectName: tag
                textKey: modelData.textKey
                density: "compact"
                checkable: false
                checked: Session.settings[modelData.setting]
                onClicked: Session.command("setting", modelData.setting, (!Session.settings[modelData.setting]).toString())
            }
        }
    }
    UG.UiText {
        tag: filters.tag + ".hint"
        textKey: "minecraft.version_types_hint"
        typographyRole: "caption"
        visible: filters.showHint
        Layout.fillWidth: true
        wrapMode: Text.Wrap
    }
}
