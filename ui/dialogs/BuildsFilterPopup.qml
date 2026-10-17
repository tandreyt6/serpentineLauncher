import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

UG.PopupPanel {
    id: filters
    onOpened: { nameSearch.forceActiveFocus(); nameSearch.selectAll() }
    required property var page
    parent: page
    height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, parent ? parent.height : Style.value(page.appearance, "buildsPageHeight3"))

    tag: "ui.pages.buildspage.20"
    objectName: "builds.filter.popup"
    x: page.appearance.pageMargin
    y: page.appearance.pageMargin + page.appearance.controlHeight + 6
    width: Style.value(page.appearance, "buildsPageWidth4")
    padding: page.appearance.dialogPadding
    background: UG.Frame {
        tag: "ui.pages.buildspage.21"
        padding: 0
        displayText: ""
        useDisplayText: true
    }
    contentItem: ColumnLayout {
        spacing: Style.value(page.appearance, "buildsPageSpacing")
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: page.appearance.layoutGap
            rowSpacing: page.appearance.smallGap
            UG.UiText {
                tag: "ui.pages.buildspage.22"
                verticalAlignment: Text.AlignVCenter
                textKey: "builds.title"
                typographyRole: (true) ? "caption" : "body"
            }
            UG.UiText {
                tag: "ui.pages.buildspage.23"
                verticalAlignment: Text.AlignVCenter
                textKey: "builds.id"
                typographyRole: (true) ? "caption" : "body"
            }
            UG.TextField {
                tag: "ui.pages.buildspage.24"
                id: nameSearch
                displayText: ""
                useDisplayText: true
                objectName: "builds.search"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: page.search
                onTextEdited: page.search = text
            }
            UG.TextField {
                tag: "ui.pages.buildspage.25"
                displayText: ""
                useDisplayText: true
                objectName: "builds.filter.id"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: page.filterId
                onTextEdited: page.filterId = text
            }
            UG.UiText {
                tag: "ui.pages.buildspage.26"
                verticalAlignment: Text.AlignVCenter
                textKey: "builds.minecraft"
                typographyRole: (true) ? "caption" : "body"
            }
            UG.UiText {
                tag: "ui.pages.buildspage.27"
                verticalAlignment: Text.AlignVCenter
                textKey: "builds.loader"
                typographyRole: (true) ? "caption" : "body"
            }
            UG.ComboBox {
                id: selection0
                density: "compact"
                tag: "ui.pages.buildspage.28"
                valueRole: "key"
                textRole: "text"
                secondaryRole: "secondary"
                textKey: "common.all"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                model: {
                    const options = (function () {
                            Session.revision
                            return [
                                {
                                    value: "",
                                    pinned: true,
                                    label: Session.text("common.all")
                                }
                            ].concat(page.minecraftVersions.map(version => ({
                                        value: version,
                                        label: version
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
                selectedKey: (page.filterMinecraft) || "__all__"
                onSelectionRequested: selected => {
                    const value = selected === "__all__" ? "" : selected
                    page.filterMinecraft = value
                }
            }
            UG.ComboBox {
                id: selection1
                density: "compact"
                tag: "ui.pages.buildspage.29"
                valueRole: "key"
                textRole: "text"
                secondaryRole: "secondary"
                textKey: "common.all"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                model: {
                    const options = (function () {
                            Session.revision
                            return [
                                {
                                    value: "",
                                    pinned: true,
                                    label: Session.text("common.all")
                                }
                            ].concat(["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"].map(loader => ({
                                        value: loader,
                                        label: loader
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
                selectedKey: (page.filterLoader) || "__all__"
                onSelectionRequested: selected => {
                    const value = selected === "__all__" ? "" : selected
                    page.filterLoader = value
                }
            }
            UG.UiText {
                tag: "ui.pages.buildspage.30"
                verticalAlignment: Text.AlignVCenter
                textKey: "builds.loader_version"
                typographyRole: (true) ? "caption" : "body"
            }
            UG.UiText {
                tag: "ui.pages.buildspage.31"
                verticalAlignment: Text.AlignVCenter
                textKey: "builds.state"
                typographyRole: (true) ? "caption" : "body"
            }
            UG.ComboBox {
                id: selection2
                density: "compact"
                tag: "ui.pages.buildspage.32"
                valueRole: "key"
                textRole: "text"
                secondaryRole: "secondary"
                textKey: "common.all"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                model: {
                    const options = (function () {
                            Session.revision
                            return [
                                {
                                    value: "",
                                    pinned: true,
                                    label: Session.text("common.all")
                                }
                            ].concat(page.loaderVersions.map(version => ({
                                        value: version,
                                        label: version
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
                selectedKey: (page.filterLoaderVersion) || "__all__"
                enabled: page.loaderVersions.length > 0
                onSelectionRequested: selected => {
                    const value = selected === "__all__" ? "" : selected
                    page.filterLoaderVersion = value
                }
            }
            UG.ComboBox {
                id: selection3
                density: "compact"
                tag: "ui.pages.buildspage.33"
                valueRole: "key"
                textRole: "text"
                secondaryRole: "secondary"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                model: {
                    const options = (function () {
                            Session.revision
                            return ["all", "running", "idle"].map(state => ({
                                        value: state,
                                        label: Session.text("builds.state." + state)
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
                selectedKey: (page.filterState) || "__all__"
                onSelectionRequested: selected => {
                    const value = selected === "__all__" ? "" : selected
                    page.filterState = value
                }
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            UG.Button {
                id: button8
                implicitWidth: Math.max(Style.value(page.appearance, "buildsPageImplicitWidth"), metrics8.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics8
                    text: button8.text
                    font.family: button8.appearance.fontFamily
                    font.pixelSize: button8.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.buildspage.34"
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
                    }["common.reset"] || ""] || ""
                textKey: "common.reset"
                onClicked: page.resetFilters()
            }
            UG.Button {
                id: button9
                implicitWidth: Math.max(Style.value(page.appearance, "buildsPageImplicitWidth"), metrics9.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics9
                    text: button9.text
                    font.family: button9.appearance.fontFamily
                    font.pixelSize: button9.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.buildspage.35"
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
                    }["common.close"] || ""] || ""
                textKey: "common.close"
                onClicked: filters.close()
            }
        }
    }
}
