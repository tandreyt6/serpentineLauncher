import QtQuick
import Working.Gui as UG

UG.TextField {
    id: field
    required property string settingKey
    readonly property var limits: Session.settingRanges[settingKey]
    readonly property string savedValue: Session.settings[settingKey]
    property string pendingValue: ""
    onSavedValueChanged: {
        if (savedValue === pendingValue)
            pendingValue = ""
    }
    text: pendingValue.length ? pendingValue : savedValue
    maximumLength: String(limits[1]).length
    validator: IntValidator {
        bottom: field.limits[0]
        top: field.limits[1]
    }
    onEditingFinished: {
        // Keep the submitted value visible until the asynchronous store acknowledges it.
        if (acceptableInput && text !== (pendingValue.length ? pendingValue : savedValue)) {
            pendingValue = text
            Session.command("setting", settingKey, pendingValue)
        }
        text = Qt.binding(function () { return pendingValue.length ? pendingValue : savedValue })
    }
}
