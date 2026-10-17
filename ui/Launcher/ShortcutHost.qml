import QtQuick
import QtQuick.Controls as QC

Item {
    id: host
    required property string contextKey
    objectName: "shortcuts." + contextKey
    property bool popupScope: false
    readonly property bool blocked: !popupScope && !!QC.Overlay.overlay && QC.Overlay.overlay.visible
    signal triggered(string action)
    Repeater {
        model: Session.shortcutActions.filter(action => action.scopes.includes(host.contextKey))
        delegate: Item {
            required property var modelData
            readonly property string binding: Session.settings["shortcut." + modelData.key]
            Shortcut {
                objectName: "shortcut." + host.contextKey + "." + modelData.key
                sequences: binding.length ? binding.endsWith("Return") ? [binding, binding.slice(0, -6) + "Enter"] : [binding] : []
                context: Qt.WindowShortcut
                enabled: host.enabled && host.visible && !!host.Window.window && host.Window.window.active && !host.blocked && binding.length > 0
                autoRepeat: false
                onActivated: host.triggered(modelData.key)
            }
        }
    }
}
