import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import Working.Gui as UG
import Launcher

UG.Page {
    id: page
    function handleShortcut(action) {
        if (action === "refresh" && !Session.catalogueUpdating) {
            Session.updateCatalogue()
            return true
        }
        return false
    }
    tag: "ui.page"
    objectName: "page.cores"
    property string filter: "all"
    property string deletingId: ""
    property string minecraft: ""
    property string loader: ""
    function request() {
        if (visible)
            Session.browseCores(filter, loader, minecraft)
    }
    onFilterChanged: request()
    onMinecraftChanged: request()
    onLoaderChanged: request()
    onVisibleChanged: {
        if (visible)
            request()
    }
    Component.onCompleted: { ThemeUI.restorePageState(page, "page.cores"); request() }
    Connections {
        target: Session
        function onChanged() {
            if (!Session.live)
                page.request()
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: page.appearance.pageMargin
        spacing: page.appearance.layoutGap
        RowLayout {
            Layout.fillWidth: true
            UG.ComboBox {
                id: selection0
                density: "compact"
                tag: "ui.pages.corespage.1"
                valueRole: "key"
                textRole: "text"
                secondaryRole: "secondary"
                objectName: "cores.filter.state"
                model: {
                    const options = (function () {
                            Session.revision
                            return [
                                {
                                    value: "all",
                                    label: Session.text("common.all")
                                },
                                {
                                    value: "installed",
                                    label: Session.text("cores.installed")
                                },
                                {
                                    value: "available",
                                    label: Session.text("cores.available")
                                }
                            ]
                        })()
                    return options.map(option => ({
                                key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                text: option.label === undefined ? option.text : option.label,
                                secondary: option.note || option.secondary || "",
                                pinned: !!option.pinned,
                                enabled: option.enabled !== false
                            }))
                }
                selectedKey: (page.filter) || "__all__"
                onSelectionRequested: selected => {
                    const value = selected === "__all__" ? "" : selected
                    page.filter = value
                }
                Layout.preferredWidth: Style.value(page.appearance, "coresPagePreferredWidth")
            }
            UG.ComboBox {
                id: selection1
                density: "compact"
                tag: "ui.pages.corespage.2"
                valueRole: "key"
                textRole: "text"
                secondaryRole: "secondary"
                textKey: "common.all"

                objectName: "cores.filter.minecraft"
                Layout.preferredWidth: Style.value(page.appearance, "coresPagePreferredWidth2")
                searchable: true

                Accessible.name: Session.text("builds.minecraft")
                model: {
                    const options = (function () {
                            Session.revision
                            const installed = Session.installedCoreVersions
                            const versions = installed.concat(Session.coreBrowserVersions.filter(v => !installed.includes(v)))
                            return [
                                {
                                    value: "",
                                    pinned: true,
                                    label: Session.text("common.all")
                                }
                            ].concat(versions.map(v => ({
                                        value: v,
                                        label: v
                                    })))
                        })()
                    return options.map(option => ({
                                key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                text: option.label === undefined ? option.text : option.label,
                                secondary: option.note || option.secondary || "",
                                pinned: !!option.pinned,
                                enabled: option.enabled !== false
                            }))
                }
                selectedKey: (page.minecraft) || "__all__"
                onSelectionRequested: selected => {
                    const value = selected === "__all__" ? "" : selected
                    page.minecraft = value
                }
            }
            UG.ComboBox {
                id: selection2
                density: "compact"
                tag: "ui.pages.corespage.3"
                valueRole: "key"
                textRole: "text"
                secondaryRole: "secondary"
                textKey: "common.all"
                objectName: "cores.filter.loader"
                Layout.preferredWidth: Style.value(page.appearance, "coresPagePreferredWidth3")
                model: {
                    const options = (function () {
                            Session.revision
                            return [
                                {
                                    value: "",
                                    pinned: true,
                                    label: Session.text("common.all")
                                }
                            ].concat(["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"].map(v => ({
                                        value: v,
                                        label: v
                                    })))
                        })()
                    return options.map(option => ({
                                key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                text: option.label === undefined ? option.text : option.label,
                                secondary: option.note || option.secondary || "",
                                pinned: !!option.pinned,
                                enabled: option.enabled !== false
                            }))
                }
                selectedKey: (page.loader) || "__all__"
                onSelectionRequested: selected => {
                    const value = selected === "__all__" ? "" : selected
                    page.loader = value
                }
            }
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value(page.appearance, "coresPageImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.corespage.4"
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
                    }["common.refresh"] || ""] || ""
                visible: Session.live
                textKey: "common.refresh"
                enabled: !Session.catalogueUpdating
                onClicked: Session.updateCatalogue()
            }
            Item {
                Layout.fillWidth: true
            }
            UG.Button {
                id: button1
                implicitWidth: Math.max(Style.value(page.appearance, "coresPageImplicitWidth"), metrics1.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics1
                    text: button1.text
                    font.family: button1.appearance.fontFamily
                    font.pixelSize: button1.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.corespage.5"
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
                    }[Session.settings.coreView === "cards" ? "common.cards" : "common.list"] || ""] || ""
                objectName: "cores.view"
                textKey: Session.settings.coreView === "cards" ? "common.cards" : "common.list"
                onClicked: Session.command("setting", "coreView", Session.settings.coreView === "cards" ? "list" : "cards")
            }
        }
        UG.CollectionArea {
            id: coreView
            tag: "ui.core.collection"
            objectName: "cores.grid"
            Layout.fillWidth: true
            Layout.fillHeight: true
            mode: Session.settings.coreView === "list" ? "list" : "grid"
            readonly property int columnCount: Math.max(1, Math.floor(availableWidth / (page.appearance.coreMinimumWidth + appearance.spacing)))
            elementWidth: availableWidth > 0 ? Math.max(1, Math.floor(availableWidth / columnCount) - appearance.spacing) : page.appearance.coreMinimumWidth
            elementHeight: page.appearance.coreCardHeight
            rowHeight: page.appearance.coreListHeight
            model: Session.coreBrowserModel
            keyRole: "id"
            textRole: "loader"
            Connections {
                target: coreView.viewport
                function onAtYEndChanged() {
                    if (coreView.viewport.atYEnd && page.visible && Session.coreBrowserMore)
                        Session.loadMoreCores()
                }
            }
            delegate: Component {
                UG.Frame {
                    id: coreCard
                    tag: "ui.pages.corespage.6"
                    padding: 0
                    displayText: ""
                    useDisplayText: true
                    readonly property var modelData: {
                        Session.coreBrowserModel.dataRevision

                        return Object.assign({ id: "", minecraft: "", loader: "", version: "", installed: false, progress: -1, paused: false, stage: "" }, Session.coreBrowserModel.entry(collectionContext.key))
                    }
                    readonly property bool protectedCore: Session.settings.safeMode && Session.builds.some(build => build.running && build.minecraft === modelData.minecraft && build.loader === modelData.loader && build.loader_version === modelData.version)
                    objectName: "core.card." + modelData.id

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: page.appearance.cardPadding
                        spacing: page.appearance.smallGap
                        RowLayout {
                            Layout.fillWidth: true
                            UG.UiText {
                                tag: "ui.pages.corespage.7"
                                verticalAlignment: Text.AlignVCenter
                                displayText: modelData.loader
                                font.pixelSize: Style.value(page.appearance, "coresPagePixelSize")
                                font.weight: Font.DemiBold
                            }
                            Item {
                                Layout.fillWidth: true
                            }
                            UG.UiText {
                                tag: "ui.pages.corespage.8"
                                verticalAlignment: Text.AlignVCenter
                                textKey: modelData.installed ? "cores.installed" : modelData.paused ? "downloads.paused" : modelData.progress >= 0 ? "cores.downloading" : "cores.available"
                                color: modelData.installed ? page.appearance.accent : page.appearance.muted
                                font.pixelSize: Style.value(page.appearance, "coresPagePixelSize2")
                            }
                        }
                        UG.UiText {
                            tag: "ui.pages.corespage.9"
                            verticalAlignment: Text.AlignVCenter
                            displayText: { Session.revision; return Session.formatText("common.game_version", {version: modelData.minecraft}) + (modelData.version ? " · " + modelData.version : "") }
                            typographyRole: (true) ? "caption" : "body"
                            font.pixelSize: Style.value(page.appearance, "coresPagePixelSize3")
                        }
                        UG.UiText {
                            tag: "ui.pages.corespage.10"
                            verticalAlignment: Text.AlignVCenter
                            Layout.fillWidth: true
                            displayText: modelData.stage
                            visible: modelData.stage.length > 0 && modelData.progress >= 0
                            typographyRole: (true) ? "caption" : "body"
                            font.pixelSize: Style.value(page.appearance, "coresPagePixelSize3")
                            wrapMode: Text.NoWrap
                            elide: Text.ElideRight
                        }
                        Item {
                            Layout.fillHeight: true
                            visible: Session.settings.coreView !== "list"
                        }
                        UG.ProgressBar {
                            tag: "ui.core.progress"
                            objectName: "core.progress." + modelData.id
                            Layout.fillWidth: true
                            visible: modelData.progress >= 0
                            from: 0
                            to: 100
                            value: modelData.progress
                            paused: modelData.paused
                        }
                        UG.Button {
                            id: button2
                            implicitWidth: Math.max(Style.value(page.appearance, "coresPageImplicitWidth"), metrics2.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                            TextMetrics {
                                id: metrics2
                                text: button2.text
                                font.family: button2.appearance.fontFamily
                                font.pixelSize: button2.appearance.fontSize
                                font.weight: Font.DemiBold
                            }

                            tag: "ui.pages.corespage.11"
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
                                }["cores.download"] || ""] || ""
                            visible: !modelData.installed && modelData.progress < 0
                            textKey: "cores.download"
                            onClicked: Session.command("download", modelData.id)
                        }
                        RowLayout {
                            spacing: Style.value(page.appearance, "coresPageSpacing")
                            visible: modelData.progress >= 0
                            objectName: "core.download." + modelData.id
                            UG.ToolButton {
                                tag: "ui.download.pause"
                                stateKey: "secondary"
                                displayText: ""
                                useDisplayText: true
                                iconSource: IconSources[(modelData.paused) ? "play" : "pause"] || ""
                                Accessible.name: Session.text(modelData.paused ? "downloads.resume" : "downloads.pause")
                                tooltipKey: modelData.paused ? "downloads.resume" : "downloads.pause"
                                onActivated: Session.command("pause_download", modelData.id)
                            }
                            UG.ToolButton {
                                tag: "ui.download.cancel"
                                stateKey: "secondary"
                                displayText: ""
                                useDisplayText: true
                                iconSource: IconSources["close"] || ""
                                Accessible.name: Session.text("downloads.cancel")
                                tooltipKey: "downloads.cancel"
                                onActivated: Session.command("cancel_download", modelData.id)
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            visible: modelData.installed
                            UG.Button {
                                id: button3
                                implicitWidth: Math.max(Style.value(page.appearance, "coresPageImplicitWidth"), metrics3.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                TextMetrics {
                                    id: metrics3
                                    text: button3.text
                                    font.family: button3.appearance.fontFamily
                                    font.pixelSize: button3.appearance.fontSize
                                    font.weight: Font.DemiBold
                                }

                                tag: "ui.pages.corespage.12"
                                stateKey: (false) ? "primary" : "secondary"
                                objectName: "core.open." + modelData.id
                                textKey: "cores.open_folder"
                                iconSource: IconSources["folder-open"] || ""
                                onClicked: Session.command("open_core_folder", modelData.id)
                            }
                            Item {
                                Layout.fillWidth: true
                            }
                            UG.Button {
                                id: button4
                                implicitWidth: Math.max(Style.value(page.appearance, "coresPageImplicitWidth"), metrics4.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                TextMetrics {
                                    id: metrics4
                                    text: button4.text
                                    font.family: button4.appearance.fontFamily
                                    font.pixelSize: button4.appearance.fontSize
                                    font.weight: Font.DemiBold
                                }

                                tag: "ui.pages.corespage.13"
                                stateKey: (false) ? "primary" : "secondary"
                                displayText: ""
                                useDisplayText: true
                                objectName: "core.delete." + modelData.id
                                iconSource: IconSources["delete"] || ""
                                width: Style.value(page.appearance, "coresPageWidth")
                                Accessible.name: Session.text("common.delete")
                                enabled: !coreCard.protectedCore
                                onClicked: {
                                    page.deletingId = modelData.id
                                    deleteCore.detail = modelData.loader + " · " + modelData.minecraft
                                    deleteCore.open()
                                }
                            }
                        }
                    }
                }
            }
        }
        UG.Button {
            id: button5
            implicitWidth: Math.max(Style.value(page.appearance, "coresPageImplicitWidth"), metrics5.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
            TextMetrics {
                id: metrics5
                text: button5.text
                font.family: button5.appearance.fontFamily
                font.pixelSize: button5.appearance.fontSize
                font.weight: Font.DemiBold
            }

            tag: "ui.pages.corespage.14"
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
                }["common.more"] || ""] || ""
            textKey: "common.more"
            visible: Session.coreBrowserMore
            enabled: !Session.coreBrowserBusy
            Layout.alignment: Qt.AlignHCenter
            onClicked: Session.loadMoreCores()
        }
    }
    UG.ConfirmationDialog {
        id: deleteCore
        tag: "ui.pages.corespage.15"
        actions: [
            {
                key: "cancel",
                text_key: "common.cancel"
            },
            {
                key: "accept",
                text_key: "common.delete",
                state_key: "danger"
            }
        ]
        defaultAction: "accept"
        cancelAction: "cancel"
        objectName: "cores.delete.dialog"
        heading: Session.text("cores.delete_title")
        message: Session.text("cores.delete_hint")
        onActionRequested: action => {
            if (action === "accept")
                Session.command("delete_core", page.deletingId)
        }
    }
}
