import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher

UG.Page {
    id: page
    tag: "editor.mod_catalog.page"
    objectName: "editor.mods.catalog.tab"
    required property string buildId
    required property string workspaceKey
    property string contentKind: "mod"
    readonly property var browser: Session.modBrowser(buildId, contentKind)
    readonly property var buildData: { Session.builds; return Session.build(buildId) }
    readonly property bool syncing: browser.queueModel.syncing
    readonly property bool protectedBuild: contentKind === "mod" && Session.settings.safeMode && buildData.running
    property bool filtersOpen: false
    function handleShortcut(action) {
        if (action === "find") {
            search.forceActiveFocus()
            search.selectAll()
        } else if (action === "refresh") {
            if (!browser.busy)
                browser.search(search.text)
        } else if (action === "back") {
            Editors.requestCloseTab(buildId + ":" + contentKind + "-catalog")
        } else
            return false
        return true
    }

    function requestMore() {
        if (visible && browser.more && !browser.busy && !browser.error
                && results.viewport.contentY + results.viewport.height >= results.viewport.contentHeight - results.rowHeight * 2)
            browser.loadMore()
    }
    Component.onCompleted: browser.open()
    onVisibleChanged: if (visible) { browser.open(); Qt.callLater(requestMore) }
    Connections {
        target: page.browser
        function onChanged() { Qt.callLater(page.requestMore) }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Style.value(page.appearance, "modCatalogMargins")
        spacing: Style.value(page.appearance, "modCatalogSpacing")
        UG.Button {
            tag: "editor.mod_catalog.back"
            objectName: "mod.catalog.back"
            textKey: "editor.mod_back"
            iconSource: IconSources.back || ""
            implicitWidth: Style.value(page.appearance, "modCatalogImplicitWidth")
            onClicked: Editors.command("close_tab", page.buildId + ":" + page.contentKind + "-catalog", page.workspaceKey)
        }
        UG.SplitView {
            id: split
            tag: "editor.mod_catalog.split"
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: width < 760 ? Qt.Vertical : Qt.Horizontal
            minimumSizes: orientation === Qt.Horizontal ? [280, 240] : [180, 140]
            proportions: [0.68, 0.32]
            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Style.value(page.appearance, "modCatalogMargins2")
                    anchors.rightMargin: split.orientation === Qt.Horizontal ? Style.value(page.appearance, "modCatalogRightMargin") : Style.value(page.appearance, "modCatalogRightMargin2")
                    anchors.bottomMargin: split.orientation === Qt.Vertical ? Style.value(page.appearance, "modCatalogBottomMargin") : Style.value(page.appearance, "modCatalogBottomMargin2")
                    spacing: Style.value(page.appearance, "modCatalogSpacing2")
                    RowLayout {
                        Layout.fillWidth: true
                        UG.TextField {
                            id: search
                            tag: "editor.mod_catalog.search"
                            objectName: "mod.catalog.search"
                            Layout.fillWidth: true
                            textKey: "common.search"
                            text: page.browser.query
                            onAccepted: page.browser.search(text)
                        }
                        UG.Button {
                            tag: "editor.mod_catalog.search_action"
                            objectName: "mod.catalog.search.action"
                            textKey: "common.search_action"
                            iconSource: IconSources.search || ""
                            onClicked: page.browser.search(search.text)
                        }
                        UG.Button {
                            tag: "editor.mod_catalog.filters"
                            textKey: "editor.mod_filters"
                            onClicked: { page.filtersOpen = !page.filtersOpen; if (page.filtersOpen) page.browser.requestFilters() }
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: page.filtersOpen ? Style.value(page.appearance, "modCatalogPreferredHeight") : 0
                        clip: true
                        visible: Layout.preferredHeight > 0
                        Behavior on Layout.preferredHeight { NumberAnimation { duration: Session.settings.reducedMotion ? 0 : Style.value(page.appearance, "modCatalogDuration"); easing.type: Easing.OutCubic } }
                        Loader {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            height: Style.value(page.appearance, "modCatalogHeight")
                            active: page.filtersOpen
                            sourceComponent: Component { ModFilters {
                            catalogue: true
                            contentKind: page.contentKind
                            minecraft: page.browser.minecraft
                            loader: page.browser.loader
                            categories: page.browser.categories
                            category: page.browser.category
                            sort: page.browser.sort
                            onApply: (minecraft, loader, category, sort, channel) => page.browser.setFilters(category, sort, minecraft, loader)
                            } }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        visible: page.browser.error.length > 0
                        UG.UiText {
                            tag: "editor.mod_catalog.error"
                            Layout.fillWidth: true
                            displayText: page.browser.error
                            wrapMode: Text.Wrap
                        }
                        UG.Button {
                            tag: "editor.mod_catalog.retry"
                            textKey: "common.retry"
                            enabled: !page.browser.busy
                            onClicked: page.browser.retry()
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        UG.CollectionArea {
                            id: results
                            tag: "editor.mod_catalog.results"
                            objectName: "mod.catalog.results"
                            anchors.fill: parent
                            mode: "list"
                            rowHeight: 108
                            model: page.browser.model
                            Connections {
                                target: results.viewport
                                function onContentYChanged() { page.requestMore() }
                                function onHeightChanged() { Qt.callLater(page.requestMore) }
                                function onContentHeightChanged() { Qt.callLater(page.requestMore) }
                            }
                            delegate: Component {
                                UG.Frame {
                                    id: entry
                                    tag: "editor.mod_catalog.entry"
                                    readonly property var mod: collectionContext.detail || ({id: "", title: "", description: "", author: "", downloads: 0})
                                    readonly property bool queued: { if (!page || !page.browser) return false; page.browser.queue; return page.browser.isQueued(mod.id) }
                                    objectName: "mod.catalog." + mod.id
                                    padding: Style.value(page.appearance, "modCatalogPadding")
                                    HoverHandler { id: rowHover }
                                    TapHandler {
                                        acceptedButtons: Qt.LeftButton
                                        gesturePolicy: TapHandler.DragThreshold
                                        onTapped: Editors.openContent(page.buildId, entry.mod.id, page.contentKind, page.workspaceKey)
                                    }
                                    RowLayout {
                                        anchors.fill: parent
                                        spacing: Style.value(page.appearance, "modCatalogSpacing")
                                        Item {
                                            Layout.preferredWidth: Style.value(page.appearance, "modCatalogPreferredWidth")
                                            Layout.preferredHeight: Style.value(page.appearance, "modCatalogPreferredHeight2")
                                            Image {
                                                anchors.fill: parent
                                                source: entry.mod.icon || ""
                                                sourceSize: Qt.size(Style.value(page.appearance, "modCatalogSourceSize"), Style.value(page.appearance, "modCatalogSourceSize"))
                                                asynchronous: true
                                                fillMode: Image.PreserveAspectFit
                                                opacity: status === Image.Ready ? 1 : 0
                                                Behavior on opacity { NumberAnimation { duration: Session.settings.reducedMotion ? 0 : Style.value(page.appearance, "modCatalogDuration") } }
                                            }
                                            UG.Icon {
                                                tag: "editor.mod_catalog.entry.placeholder"
                                                anchors.centerIn: parent
                                                source: IconSources[page.contentKind === "shader" ? "shaders" : page.contentKind === "resourcepack" ? "resource-packs" : "mods"] || ""
                                                visible: !entry.mod.icon
                                            }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            spacing: Style.value(page.appearance, "modCatalogSpacing3")
                                            UG.UiText {
                                                tag: "editor.mod_catalog.entry.title"
                                                Layout.fillWidth: true
                                                displayText: entry.mod.title
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                            }
                                            UG.UiText {
                                                tag: "editor.mod_catalog.entry.description"
                                                Layout.fillWidth: true
                                                Layout.fillHeight: true
                                                displayText: entry.mod.description
                                                wrapMode: Text.Wrap
                                                maximumLineCount: Style.value(page.appearance, "modCatalogMaximumLineCount")
                                                elide: Text.ElideRight
                                            }
                                            RowLayout {
                                                Layout.fillWidth: true
                                                UG.UiText {
                                                    tag: "editor.mod_catalog.entry.author"
                                                    Layout.fillWidth: true
                                                    displayText: entry.mod.author
                                                    elide: Text.ElideRight
                                                }
                                                UG.UiText {
                                                    tag: "editor.mod_catalog.entry.downloads"
                                                    displayText: "↓ " + Number(entry.mod.downloads).toLocaleString(Qt.locale(), 'f', 0)
                                                }
                                            }
                                        }
                                        UG.Button {
                                            id: add
                                            tag: "editor.mod_catalog.entry.enqueue"
                                            objectName: "mod.enqueue." + entry.mod.id
                                            textKey: "editor.choose_mod_version"
                                            opacity: rowHover.hovered ? 1 : Style.value(page.appearance, "modCatalogOpacity")
                                            Behavior on opacity { NumberAnimation { duration: Session.settings.reducedMotion ? 0 : Style.value(page.appearance, "modCatalogDuration2") } }
                                            implicitWidth: metrics.advanceWidth + appearance.controlPadding * 2
                                            TextMetrics {
                                                id: metrics
                                                text: add.text
                                                font.family: add.appearance.fontFamily
                                                font.pixelSize: add.appearance.fontSize
                                                font.weight: Font.DemiBold
                                            }
                                            onClicked: Editors.openContent(page.buildId, entry.mod.id, page.contentKind, page.workspaceKey)
                                        }
                                    }
                                }
                            }
                        }
                        UG.UiText {
                            tag: "editor.mod_catalog.empty"
                            anchors.centerIn: parent
                            visible: !results.count && !page.browser.busy && !page.browser.error
                            textKey: page.contentKind === "mod" ? "editor.mod_catalog.empty" : "editor.content_catalog_empty"
                        }
                    }
                    UG.UiText {
                        tag: "editor.mod_catalog.loading"
                        visible: page.browser.busy
                        textKey: "common.loading"
                    }
                }
            }
            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Style.value(page.appearance, "modCatalogMargins2")
                    anchors.leftMargin: split.orientation === Qt.Horizontal ? Style.value(page.appearance, "modCatalogLeftMargin") : Style.value(page.appearance, "modCatalogLeftMargin2")
                    anchors.topMargin: split.orientation === Qt.Vertical ? Style.value(page.appearance, "modCatalogTopMargin") : Style.value(page.appearance, "modCatalogTopMargin2")
                    spacing: Style.value(page.appearance, "modCatalogSpacing2")
                    UG.UiText {
                        tag: "editor.mod_catalog.queue.heading"
                        textKey: "editor.mod_queue"
                        font.weight: Font.DemiBold
                    }
                    UG.CollectionArea {
                        tag: "editor.mod_catalog.queue"
                        objectName: "mod.catalog.queue"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        mode: "list"
                        rowHeight: page.browser.queueModel.hasDependencies ? 104 : 80
                        model: page.browser.queueModel
                        delegate: Component {
                            ContentQueueRow {
                                entryData: collectionContext.detail || ({id: "", title: "", state: "queued", owner_id: ""})
                                protectedBuild: page.protectedBuild
                                onRemoveRequested: key => page.browser.remove(key)
                            }
                        }
                    }
                    UG.Button {
                        tag: "editor.mod_catalog.queue.sync"
                        objectName: "mod.catalog.synchronize"
                        Layout.fillWidth: true
                        stateKey: "primary"
                        textKey: "editor.sync_mods"
                        enabled: page.browser.queueModel.count > 0 && !page.syncing && !page.protectedBuild
                        disabledExplanation: page.protectedBuild ? Session.text("notice.locked") : ""
                        onClicked: page.browser.synchronize()
                    }
                }
            }
        }
    }
}
