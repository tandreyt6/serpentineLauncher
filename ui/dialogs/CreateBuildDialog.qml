import "../Launcher/Style.js" as Style
import QtQuick
import Working.Gui as UG
import QtQuick.Layouts
import QtQuick.Controls as QC
import Launcher

UG.PopupPanel {
    id: dialog
    parent: QC.Overlay.overlay
    height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, Math.max(0, parent ? parent.height - 2 * padding : Style.value(dialog.appearance, "createBuildDialogHeight")))
    tag: "ui.dialogs.createbuilddialog.1"
    objectName: "dialog.createBuild"
    property bool idEdited: false
    property string selectedLoader: Session.live ? "Vanilla" : "Fabric"
    property string selectedMinecraft: Session.live ? (Session.minecraftVersions.length ? Session.minecraftVersions[0] : "") : "1.21.1"
    property string selectedLoaderVersion: Session.live ? "" : "0.16.10"
    property string error: ""
    function versionOptions(values, loader, minecraft) {
        Session.coreChoicesRevision
        const installed = new Set(Session.versionOptions(loader, minecraft).filter(option => option.note.length).map(option => option.value))
        const installedLabel = Session.text("cores.installed")
        return values.map(version => ({
                    value: version,
                    label: version,
                    note: installed.has(version) ? installedLabel : ""
                }))
    }
    property var loaderOptions: []
    readonly property var versions: Session.live ? loaderOptions.map(option => option.value) : selectedLoader === "Fabric" ? ["0.16.10", "0.16.9"] : selectedLoader === "Forge" ? ["47.3.0", "47.2.0"] : selectedLoader === "NeoForge" ? ["21.1.115", "21.1.90"] : ["0.27.1", "0.26.0"]
    readonly property bool versionsBusy: (Session.catalogueUpdating, Session.versionCatalogueRevision, Session.catalogueBusy(selectedLoader, selectedMinecraft))
    readonly property var minecraftVersions: {
        Session.settings
        return Session.filterMinecraftVersions(Session.live ? Session.minecraftVersions : selectedLoader === "Vanilla" ? ["1.21.4", "1.21.1", "1.20.1"] : selectedLoader === "Forge" ? ["1.20.1"] : ["1.21.1"])
    }
    function reconcileVersionSelection() {
        if (!versionsBusy && !versions.includes(selectedLoaderVersion))
            selectedLoaderVersion = versions.length ? versions[0] : ""
    }
    onVersionsChanged: reconcileVersionSelection()
    onVersionsBusyChanged: reconcileVersionSelection()
    onSelectedLoaderChanged: {
        loaderOptions = []
        selectedLoaderVersion = selectedLoader === "Vanilla" ? "" : versions.length ? versions[0] : ""
        if (Session.live && visible && selectedLoader !== "Vanilla" && selectedMinecraft.length)
            Session.requestVersions(selectedLoader, selectedMinecraft)
    }
    onSelectedMinecraftChanged: {
        loaderOptions = []
        selectedLoaderVersion = selectedLoader === "Vanilla" ? "" : versions.length ? versions[0] : ""
        if (Session.live && visible && selectedLoader !== "Vanilla" && selectedMinecraft.length)
            Session.requestVersions(selectedLoader, selectedMinecraft)
    }
    onMinecraftVersionsChanged: {
        if (!minecraftVersions.includes(selectedMinecraft))
            selectedMinecraft = minecraftVersions.length ? minecraftVersions[0] : ""
    }
    modal: true
    focus: true
    anchors.centerIn: QC.Overlay.overlay
    width: Math.min(Style.value(dialog.appearance, "createBuildDialogWidth"), Math.max(0, parent ? parent.width - 2 * padding : Style.value(dialog.appearance, "createBuildDialogWidth")))
    padding: dialog.appearance.dialogPadding
    closePolicy: QC.Popup.CloseOnEscape
    background: UG.Frame {
        tag: "ui.dialogs.createbuilddialog.2"
        padding: 0
        displayText: ""
        useDisplayText: true
    }
    overlayColor: Style.value(dialog.appearance, "createBuildOverlayColor")
    onAboutToShow: {
        if (Session.live) {
            if (selectedLoader !== "Vanilla" && selectedMinecraft.length)
                Session.requestVersions(selectedLoader, selectedMinecraft)
        }
        titleField.text = ""
        idField.text = ""
        idEdited = false
        error = ""
        titleField.forceActiveFocus()
    }
    Connections {
        target: Session
        function onVersionsReady(loader, minecraft, choices) {
            if (loader === dialog.selectedLoader && minecraft === dialog.selectedMinecraft)
                dialog.loaderOptions = choices
        }
        function onCatalogueStateChanged() {
            if (dialog.visible && Session.live && dialog.selectedLoader !== "Vanilla" && dialog.selectedMinecraft.length)
                Session.requestVersions(dialog.selectedLoader, dialog.selectedMinecraft)
        }
    }
    contentItem: ColumnLayout {
        spacing: Style.value(dialog.appearance, "createBuildDialogSpacing")
        UG.UiText {
            tag: "ui.dialogs.createbuilddialog.3"
            verticalAlignment: Text.AlignVCenter
            textKey: "builds.new"
            font.pixelSize: Style.value(dialog.appearance, "createBuildDialogPixelSize")
            font.weight: Font.DemiBold
        }
        UG.UiText {
            tag: "ui.dialogs.createbuilddialog.4"
            verticalAlignment: Text.AlignVCenter
            textKey: "builds.title"
            typographyRole: (true) ? "caption" : "body"
            font.pixelSize: Style.value(dialog.appearance, "createBuildDialogPixelSize2")
        }
        UG.TextField {
            id: titleField
            tag: "ui.dialogs.createbuilddialog.5"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            objectName: "create.title"
            onTextEdited: {
                if (!dialog.idEdited)
                    idField.text = Session.safeId(text)
                dialog.error = ""
            }
        }
        UG.UiText {
            tag: "ui.dialogs.createbuilddialog.6"
            verticalAlignment: Text.AlignVCenter
            textKey: "builds.id"
            typographyRole: (true) ? "caption" : "body"
            font.pixelSize: Style.value(dialog.appearance, "createBuildDialogPixelSize2")
        }
        UG.TextField {
            id: idField
            tag: "ui.dialogs.createbuilddialog.7"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            objectName: "create.id"
            onTextEdited: {
                dialog.idEdited = true
                dialog.error = Session.validateId(text)
            }
        }
        MinecraftVersionFilters {
            tag: "create.versionTypes"
            Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Style.value(dialog.appearance, "createBuildDialogSpacing2")
            ColumnLayout {
                Layout.fillWidth: true
                UG.UiText {
                    tag: "ui.dialogs.createbuilddialog.8"
                    verticalAlignment: Text.AlignVCenter
                    textKey: "builds.minecraft"
                    typographyRole: (true) ? "caption" : "body"
                    font.pixelSize: Style.value(dialog.appearance, "createBuildDialogPixelSize2")
                }
                UG.ComboBox {
                    id: selection0
                    density: "compact"
                    tag: "ui.dialogs.createbuilddialog.9"
                    valueRole: "key"
                    textRole: "text"
                    secondaryRole: "secondary"
                    objectName: "create.minecraft"
                    textKey: dialog.minecraftVersions.length ? "common.choose" : "minecraft.version_types_empty"
                    enabled: dialog.minecraftVersions.length > 0
                    Layout.fillWidth: true
                    searchable: true
                    model: {
                        const options = (function () {
                                Session.revision
                                return dialog.versionOptions(dialog.minecraftVersions, "Vanilla", "")
                            })()
                        return options.map(option => ({
                                    key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                    text: option.label === undefined ? option.text : option.label,
                                    secondary: option.note || option.secondary || "",
                                    pinned: !!option.pinned,
                                    enabled: option.enabled !== false
                                }))
                    }
                    selectedKey: (dialog.selectedMinecraft) || "__all__"
                    onSelectionRequested: selected => {
                        const value = selected === "__all__" ? "" : selected
                        dialog.selectedMinecraft = value
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                UG.UiText {
                    tag: "ui.dialogs.createbuilddialog.10"
                    verticalAlignment: Text.AlignVCenter
                    textKey: "builds.loader"
                    typographyRole: (true) ? "caption" : "body"
                    font.pixelSize: Style.value(dialog.appearance, "createBuildDialogPixelSize2")
                }
                UG.ComboBox {
                    id: selection1
                    density: "compact"
                    tag: "ui.dialogs.createbuilddialog.11"
                    valueRole: "key"
                    textRole: "text"
                    secondaryRole: "secondary"
                    objectName: "create.loader"
                    Layout.fillWidth: true
                    model: {
                        const options = (function () {
                                return ["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"].map(v => ({
                                            value: v,
                                            label: v
                                        }))
                            })()
                        return options.map(option => ({
                                    key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                    text: option.label === undefined ? option.text : option.label,
                                    secondary: option.note || option.secondary || "",
                                    pinned: !!option.pinned,
                                    enabled: option.enabled !== false
                                }))
                    }
                    selectedKey: (dialog.selectedLoader) || "__all__"
                    onSelectionRequested: selected => {
                        const value = selected === "__all__" ? "" : selected
                        dialog.selectedLoader = value
                        if (!Session.live && value === "Forge")
                            dialog.selectedMinecraft = "1.20.1"
                        else if (!Session.live && value !== "Vanilla")
                            dialog.selectedMinecraft = "1.21.1"
                        dialog.selectedLoaderVersion = dialog.versions.length ? dialog.versions[0] : ""
                    }
                }
            }
        }
        UG.UiText {
            tag: "ui.dialogs.createbuilddialog.12"
            verticalAlignment: Text.AlignVCenter
            textKey: "builds.loader_version"
            typographyRole: (true) ? "caption" : "body"
            font.pixelSize: Style.value(dialog.appearance, "createBuildDialogPixelSize2")
            visible: dialog.selectedLoader !== "Vanilla"
        }
        UG.ComboBox {
            id: selection2
            density: "compact"
            tag: "ui.dialogs.createbuilddialog.13"
            textKey: dialog.versionsBusy ? "versions.loading" : "versions.empty"
            valueRole: "key"
            textRole: "text"
            secondaryRole: "secondary"
            objectName: "create.loaderVersion"
            Layout.fillWidth: true
            visible: dialog.selectedLoader !== "Vanilla"
            searchable: true
            enabled: dialog.versions.length > 0
            model: {
                const options = (function () {
                        Session.revision
                        return Session.live ? dialog.loaderOptions.map(option => ({
                                    value: option.value,
                                    label: option.label,
                                    note: option.installed ? Session.text("cores.installed") : ""
                                })) : dialog.versionOptions(dialog.versions, dialog.selectedLoader, dialog.selectedMinecraft)
                    })()
                return options.map(option => ({
                            key: String(option.value === undefined ? option.key : option.value) || "__all__",
                            text: option.label === undefined ? option.text : option.label,
                            secondary: option.note || option.secondary || "",
                            pinned: !!option.pinned,
                            enabled: option.enabled !== false
                        }))
            }
            selectedKey: (dialog.selectedLoaderVersion) || "__all__"
            onSelectionRequested: selected => {
                const value = selected === "__all__" ? "" : selected
                dialog.selectedLoaderVersion = value
            }
        }
        UG.UiText {
            tag: "ui.dialogs.createbuilddialog.14"
            verticalAlignment: Text.AlignVCenter
            Layout.fillWidth: true
            displayText: dialog.error
            color: dialog.appearance.danger
            visible: dialog.error.length > 0
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            Layout.topMargin: Style.value(dialog.appearance, "createBuildDialogTopMargin")
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value(dialog.appearance, "createBuildDialogImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.dialogs.createbuilddialog.15"
                stateKey: (false) ? "primary" : "secondary"
                iconSource: IconSources[{
                        "common.save": "save",
                        "common.back": "back",
                        "common.close": "close",
                        "common.cards": "view-grid",
                        "common.list": "view-list",
                        "builds.new": "add",
                        "builds.edit": "edit",
                        "builds.delete": "delete",
                        "builds.about": "info",
                        "profile.add": "add",
                        "editor.add_mod": "add",
                        "common.edit": "edit",
                        "common.delete": "delete",
                        "common.refresh": "refresh",
                        "common.add": "add"
                    }["common.cancel"] || ""] || ""
                textKey: "common.cancel"
                onClicked: dialog.close()
            }
            UG.Button {
                id: button1
                implicitWidth: Math.max(Style.value(dialog.appearance, "createBuildDialogImplicitWidth"), metrics1.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics1
                    text: button1.text
                    font.family: button1.appearance.fontFamily
                    font.pixelSize: button1.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.dialogs.createbuilddialog.16"
                stateKey: (true) ? "primary" : "secondary"
                iconSource: IconSources[{
                        "common.save": "save",
                        "common.back": "back",
                        "common.close": "close",
                        "common.cards": "view-grid",
                        "common.list": "view-list",
                        "builds.new": "add",
                        "builds.edit": "edit",
                        "builds.delete": "delete",
                        "builds.about": "info",
                        "profile.add": "add",
                        "editor.add_mod": "add",
                        "common.edit": "edit",
                        "common.delete": "delete",
                        "common.refresh": "refresh",
                        "common.add": "add"
                    }["common.create"] || ""] || ""
                textKey: "common.create"
                objectName: "create.confirm"
                enabled: dialog.selectedMinecraft.length > 0 && (dialog.selectedLoader === "Vanilla" || dialog.selectedLoaderVersion.length > 0)
                onClicked: {
                    dialog.error = Session.createBuild(titleField.text, idField.text, dialog.selectedMinecraft, dialog.selectedLoader, dialog.selectedLoader === "Vanilla" ? "" : dialog.selectedLoaderVersion)
                    if (!dialog.error.length)
                        dialog.close()
                }
            }
        }
    }
}
