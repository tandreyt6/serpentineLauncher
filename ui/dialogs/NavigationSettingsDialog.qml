import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import Working.Gui as UG
import "../settings" as Settings

UG.PopupPanel {
    id: dialog
    tag: "ui.navigation.settings"
    objectName: "navigation.settings.dialog"
    parent: QC.Overlay.overlay
    property real previewPanelWidth: 180
    property bool panelOpened: false
    readonly property bool horizontalPanel: Session.settings.panelSide === "top" || Session.settings.panelSide === "bottom"
    readonly property bool canTogglePreview: !horizontalPanel && (Session.settings.panelMode === "button" || Session.settings.panelMode === "both")
    signal previewToggleRequested()

    modal: false
    closePolicy: QC.Popup.CloseOnEscape
    focus: true
    scaleTransition: false
    width: Math.min(Style.value(dialog.appearance, "navigationSettingsDialogWidth"), Math.max(Style.value(dialog.appearance, "navigationSettingsDialogWidth2"), (parent ? parent.width : Style.value(dialog.appearance, "navigationSettingsDialogWidth3")) - 2 * ((horizontalPanel ? 0 : previewPanelWidth) + Style.value(dialog.appearance, "navigationSettingsDialogWidth4"))))
    height: Math.min(Style.value(dialog.appearance, "navigationSettingsDialogHeight"), Math.max(0, (parent ? parent.height : Style.value(dialog.appearance, "navigationSettingsDialogHeight2")) - Style.value(dialog.appearance, "navigationSettingsDialogHeight3")))
    x: parent ? (parent.width - width) / 2 : 0
    y: parent ? (parent.height - height) / 2 : 0
    contentItem: ColumnLayout {
        spacing: Style.value(dialog.appearance, "navigationSettingsDialogSpacing")
        UG.UiText {
            tag: "ui.navigation.settings.title"
            textKey: "settings.panel_setup"
            typographyRole: "heading"
            Layout.fillWidth: true
        }
        Settings.PanelSettings {
            objectName: "navigation.settings.form"
            showPreviewAction: false
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
        }
        RowLayout {
            Layout.fillWidth: true
            UG.Button {
                tag: "ui.navigation.settings.preview"
                objectName: "navigation.settings.toggle"
                textKey: dialog.panelOpened ? "settings.panel_preview_close" : "settings.panel_preview_open"
                stateKey: "secondary"
                visible: dialog.canTogglePreview
                onActivated: dialog.previewToggleRequested()
            }
            Item { Layout.fillWidth: true }
            UG.Button {
                tag: "ui.navigation.settings.done"
                objectName: "navigation.settings.done"
                textKey: "common.done"
                stateKey: "primary"
                onActivated: dialog.close()
            }
        }
    }
}
