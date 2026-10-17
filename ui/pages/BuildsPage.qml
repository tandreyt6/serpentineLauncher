import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import Working.Gui as UG
import Launcher
import "../dialogs" as Dialogs

UG.Page {
    id: page
    tag: "ui.page"
    objectName: "page.builds"
    Component.onCompleted: ThemeUI.restorePageState(page, "page.builds")
    property string search: ""
    function handleShortcut(action) {
        if (action === "find") {
            filters.open()
            return true
        }
        return false
    }
    property string filterId: ""
    property string filterMinecraft: ""
    property string filterLoader: ""
    property string filterLoaderVersion: ""
    property string filterState: "all"
    property var detailSelection: ({})
    readonly property var selection: {
        Session.builds
        return Session.build(Session.selectedId)
    }
    readonly property bool cardsMode: Session.settings.buildView === "cards"
    readonly property int cardSizeIndex: Math.max(0, Session.cardSizeOptions.findIndex(option => option.key === Session.settings.buildCardSize))

    readonly property int displayedCardSizeIndex: cardsMode ? Math.round(sizeSlider.pressed ? sizeSlider.previewValue : sizeSlider.value) : cardSizeIndex
    readonly property var cardSizeOption: Session.cardSizeOptions[displayedCardSizeIndex]
    readonly property bool largeCards: displayedCardSizeIndex >= Math.ceil(Session.cardSizeOptions.length / 2)
    readonly property int cardWidth: page.appearance[cardSizeOption.width_token]
    readonly property int cardHeight: cardWidth
    readonly property var minecraftVersions: Array.from(new Set(Session.builds.map(build => build.minecraft))).sort().reverse()
    readonly property var loaderVersions: Array.from(new Set(Session.builds.filter(build => (!filterLoader || build.loader === filterLoader) && (!filterMinecraft || build.minecraft === filterMinecraft)).map(build => build.loader_version).filter(version => version.length))).sort().reverse()
    function applyFilters() {
        Session.buildModel.setFilters(search, filterId, filterMinecraft, filterLoader, filterLoaderVersion, filterState)
    }
    function resetFilters() {
        search = ""
        filterId = ""
        filterMinecraft = ""
        filterLoader = ""
        filterLoaderVersion = ""
        filterState = "all"
    }
    onSearchChanged: applyFilters()
    onFilterIdChanged: applyFilters()
    onFilterMinecraftChanged: {
        filterLoaderVersion = ""
        applyFilters()
    }
    onFilterLoaderChanged: {
        filterLoaderVersion = ""
        applyFilters()
    }
    onFilterLoaderVersionChanged: applyFilters()
    onFilterStateChanged: applyFilters()
    onSelectionChanged: {
        if (selection.id)
            detailSelection = selection
    }
    MouseArea {
        objectName: "builds.blank.page"
        anchors.fill: parent
        z: -1
        acceptedButtons: Qt.LeftButton
        property point pressPosition: Qt.point(0, 0)
        onPressed: mouse => { pressPosition = Qt.point(mouse.x, mouse.y) }
        onClicked: mouse => {
            if (Session.selectedId.length && Math.abs(mouse.x - pressPosition.x) < Qt.styleHints.startDragDistance
                    && Math.abs(mouse.y - pressPosition.y) < Qt.styleHints.startDragDistance)
                Session.command("select", "")
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: page.appearance.pageMargin
        spacing: page.appearance.rowGap
        RowLayout {
            Layout.fillWidth: true
            spacing: page.appearance.rowGap
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value(page.appearance, "buildsPageImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.buildspage.1"
                stateKey: (false) ? "primary" : "secondary"
                objectName: "builds.filter"
                textKey: "builds.filter"
                iconSource: IconSources["search"] || ""
                checked: Session.buildModel.activeFilters > 0
                onClicked: filters.popupVisible ? filters.close() : filters.open()
            }
            UG.UiText {
                tag: "ui.pages.buildspage.2"
                verticalAlignment: Text.AlignVCenter
                displayText: Session.buildModel.count.toString()
                typographyRole: (true) ? "caption" : "body"
            }
            Item {
                Layout.fillWidth: true
            }
            UG.Button {
                id: button1
                implicitWidth: Math.max(Style.value(page.appearance, "buildsPageImplicitWidth"), metrics1.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics1
                    text: button1.text
                    font.family: button1.appearance.fontFamily
                    font.pixelSize: button1.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.buildspage.3"
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
                    }["builds.new"] || ""] || ""
                textKey: "builds.new"
                objectName: "builds.create"
                onClicked: createDialog.open()
            }
            UG.Button {
                id: button2
                implicitWidth: Math.max(Style.value(page.appearance, "buildsPageImplicitWidth"), metrics2.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics2
                    text: button2.text
                    font.family: button2.appearance.fontFamily
                    font.pixelSize: button2.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.buildspage.4"
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
                    }[page.cardsMode ? "common.cards" : "common.list"] || ""] || ""
                objectName: "builds.view"
                Layout.minimumWidth: implicitWidth
                textKey: page.cardsMode ? "common.cards" : "common.list"
                onClicked: Session.command("setting", "buildView", page.cardsMode ? "list" : "cards")
            }
            FocusScope {
                id: cardSizeHost
                objectName: "builds.cardSize.control"
                property bool expanded: false
                property real reveal: expanded ? 1 : 0
                readonly property bool reducedMotion: Boolean(Session.settings.reducedMotion)
                readonly property var previewOption: Session.cardSizeOptions[Math.round(sizeSlider.previewValue)]
                Layout.preferredWidth: cardSizeButton.implicitWidth + Style.value(page.appearance, "buildsPagePreferredWidth") * reveal
                Layout.minimumWidth: Layout.preferredWidth
                Layout.maximumWidth: Layout.preferredWidth
                Layout.preferredHeight: Style.value(page.appearance, "buildsPagePreferredHeight")
                clip: true
                onVisibleChanged: {
                    if (!visible)
                        expanded = false
                }
                onReducedMotionChanged: {
                    if (reducedMotion && sizeRevealMotion.running)
                        sizeRevealMotion.complete()
                }
                onExpandedChanged: {
                    Qt.callLater(function () {
                        if (expanded && visible)
                            sizeSlider.forceActiveFocus(Qt.PopupFocusReason)
                        else if (visible && sizeSlider.activeFocus)
                            cardSizeButton.forceActiveFocus(Qt.PopupFocusReason)
                    })
                }
                Keys.onEscapePressed: event => {
                    expanded = false
                    event.accepted = true
                }
                Behavior on reveal {
                    NumberAnimation {
                        id: sizeRevealMotion
                        duration: cardSizeHost.reducedMotion ? 0 : Style.value(page.appearance, "buildsPageDuration")
                        easing.type: Easing.OutCubic
                    }
                }
                Item {
                    anchors.right: cardSizeButton.left
                    anchors.rightMargin: Style.value(page.appearance, "buildsPageRightMargin")
                    width: Style.value(page.appearance, "buildsPageWidth")
                    height: parent.height
                    enabled: cardSizeHost.expanded && page.cardsMode
                    visible: cardSizeHost.expanded || cardSizeHost.reveal > 0
                    opacity: cardSizeHost.reveal
                    StepSlider {
                        id: sizeSlider
                        tag: "ui.build.size.slider"
                        objectName: "builds.cardSize.slider"
                        width: parent.width
                        height: Style.value(page.appearance, "buildsPageHeight")
                        handleDiameter: Style.value(page.appearance, "buildsPageHandleDiameter")
                        trackThickness: Style.value(page.appearance, "buildsPageTrackThickness")
                        tickDiameter: Style.value(page.appearance, "buildsPageTickDiameter")
                        stepCount: Session.cardSizeOptions.length
                        to: stepCount - 1
                        value: page.cardsMode ? page.cardSizeIndex : 3
                        reducedMotion: cardSizeHost.reducedMotion
                        Keys.priority: Keys.BeforeItem
                        Keys.onEscapePressed: event => {
                            cardSizeHost.expanded = false
                            event.accepted = true
                        }
                        Accessible.name: Session.text("settings.card_size")
                        onValueCommitted: chosen => {
                            const option = Session.cardSizeOptions[Math.round(chosen)]
                            if (enabled && option.key !== Session.settings.buildCardSize)
                                Session.command("setting", "buildCardSize", option.key)
                        }
                    }
                    UG.UiText {
                        tag: "ui.build.size.caption"
                        anchors.top: sizeSlider.bottom
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        typographyRole: "caption"
                        displayText: {
                            Session.revision
                            return Session.text(cardSizeHost.previewOption.text_key)
                        }
                        useDisplayText: true
                    }
                }
                UG.Button {
                    id: cardSizeButton
                    tag: "ui.build.size"
                    objectName: "builds.cardSize"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    textKey: "builds.size"
                    hideText: true
                    topPadding: 0
                    bottomPadding: 0
                    implicitWidth: sizeContent.implicitWidth + leftPadding + rightPadding
                    enabled: page.cardsMode
                    checked: cardSizeHost.expanded
                    Keys.priority: Keys.BeforeItem
                    Keys.onEscapePressed: event => {
                        cardSizeHost.expanded = false
                        event.accepted = true
                    }
                    Accessible.description: Session.text("settings.card_size") + ": " + Session.text(page.cardSizeOption.text_key)
                    onClicked: cardSizeHost.expanded = !cardSizeHost.expanded
                    onEnabledChanged: {
                        if (!enabled)
                            cardSizeHost.expanded = false
                    }
                    contentItem: RowLayout {
                        id: sizeContent
                        spacing: cardSizeButton.appearance.iconGap
                        opacity: cardSizeButton.enabled ? 1 : Style.value(page.appearance, "buildsPageOpacity")
                        UG.UiText {
                            tag: "ui.build.size.label"
                            displayText: cardSizeButton.text
                            useDisplayText: true
                            font.weight: Font.DemiBold
                        }
                        UG.Icon {
                            tag: "ui.build.size.chevron"
                            Layout.preferredWidth: Style.value(page.appearance, "buildsPagePreferredWidth2")
                            Layout.preferredHeight: Style.value(page.appearance, "buildsPagePreferredHeight2")
                            source: IconSources["chevron-down"] || ""
                            rotation: cardSizeHost.expanded ? -90 : 90
                            Behavior on rotation {
                                NumberAnimation { duration: cardSizeButton.reducedMotion ? 0 : Style.value(page.appearance, "buildsPageDuration2"); easing.type: Easing.OutCubic }
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                UG.CollectionArea {
                    id: buildsView
                    tag: "ui.build.collection"
                    objectName: "builds.viewGrid"
                    anchors.fill: parent
                    model: Session.buildModel
                    keyRole: "id"
                    textRole: "title"
                    mode: page.cardsMode ? "grid" : "list"
                    sizePreset: page.largeCards ? "normal" : "small"
                    elementWidth: page.cardWidth
                    elementHeight: page.cardHeight
                    rowHeight: page.appearance.buildListHeight
                    selectedKey: Session.selectedId
                    MouseArea {
                        objectName: "builds.blank.collection"
                        parent: buildsView.viewport.contentItem
                        x: buildsView.viewport.contentX
                        y: buildsView.viewport.contentY
                        width: buildsView.viewport.width
                        height: buildsView.viewport.height
                        z: -1
                        acceptedButtons: Qt.LeftButton
                        property point pressPosition: Qt.point(0, 0)
                        onPressed: mouse => { pressPosition = Qt.point(mouse.x, mouse.y) }
                        onClicked: mouse => {
                            if (Session.selectedId.length && Math.abs(mouse.x - pressPosition.x) < Qt.styleHints.startDragDistance
                                    && Math.abs(mouse.y - pressPosition.y) < Qt.styleHints.startDragDistance)
                                Session.command("select", "")
                        }
                    }
                    delegate: Component {
                        BuildEntry {
                            id: buildEntry
                            cardsMode: page.cardsMode
                            large: page.largeCards
                            collectionViewport: buildsView.viewport
                            geometryAnimationDuration: sizeSlider.pressed ? Style.value(page.appearance, "buildsPageGeometryAnimationDuration") : Style.value(page.appearance, "buildsPageGeometryAnimationDuration2")
                            onSelectedBuild: key => Session.command("select", key)
                            onDoubleClickedBuild: key => {
                                const action = Session.settings.buildDoubleClickAction
                                if (action === "play")
                                    buildEntry.requestPlay()
                                else if (action === "edit")
                                    Session.command("edit", key)
                                else if (action === "about")
                                    Session.command("about_build", key)
                            }
                            onContextRequested: (key, owner, x, y) => {
                                buildMenu.buildId = key
                                buildMenu.popupAt(owner, x, y, key)
                            }
                        }
                    }
                }
                UG.UiText {
                    tag: "ui.pages.buildspage.10"
                    verticalAlignment: Text.AlignVCenter
                    anchors.centerIn: parent
                    width: parent.width - Style.value(page.appearance, "buildsPageWidth2")
                    visible: Session.buildModel.count === 0
                    textKey: "builds.no_results"
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: Style.value(page.appearance, "buildsPagePixelSize")
                }
            }
            Item {
                id: detailsHost
                objectName: "builds.detailsHost"
                property real revealWidth: Session.selectedId.length > 0 ? page.appearance.detailsWidth + page.appearance.layoutGap : 0
                Layout.preferredWidth: revealWidth
                Layout.minimumWidth: revealWidth
                Layout.maximumWidth: revealWidth
                Layout.fillHeight: true
                visible: revealWidth > 0
                enabled: Session.selectedId.length > 0
                clip: true
                Behavior on revealWidth {
                    NumberAnimation {
                        duration: (Session.settings.reducedMotion ? 0 : page.appearance.duration)
                        easing.type: Easing.OutQuad
                    }
                }
                UG.Frame {
                    id: details
                    tag: "ui.pages.buildspage.11"
                    padding: 0
                    displayText: ""
                    useDisplayText: true
                    objectName: "builds.details"
                    width: page.appearance.detailsWidth
                    height: parent.height
                    x: parent.width - width
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: page.appearance.cardPadding
                        spacing: page.appearance.smallGap
                        RowLayout {
                            Layout.fillWidth: true
                            UG.UiText {
                                tag: "ui.pages.buildspage.12"
                                verticalAlignment: Text.AlignVCenter
                                Layout.fillWidth: true
                                displayText: page.detailSelection.title || ""
                                font.pixelSize: Style.value(page.appearance, "buildsPagePixelSize2")
                                font.weight: Font.DemiBold
                                wrapMode: Text.NoWrap
                            }
                            UG.Button {
                                id: button4
                                implicitWidth: Math.max(Style.value(page.appearance, "buildsPageImplicitWidth"), metrics4.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                TextMetrics {
                                    id: metrics4
                                    text: button4.text
                                    font.family: button4.appearance.fontFamily
                                    font.pixelSize: button4.appearance.fontSize
                                    font.weight: Font.DemiBold
                                }

                                tag: "ui.pages.buildspage.13"
                                stateKey: (false) ? "primary" : "secondary"
                                displayText: ""
                                useDisplayText: true
                                iconSource: IconSources["close"] || ""
                                Accessible.name: Session.text("common.close")
                                width: Style.value(page.appearance, "buildsPageWidth3")
                                height: Style.value(page.appearance, "buildsPageHeight2")
                                onClicked: Session.command("select", "")
                            }
                        }
                        UG.UiText {
                            tag: "ui.pages.buildspage.14"
                            verticalAlignment: Text.AlignVCenter
                            Layout.fillWidth: true
                            displayText: (page.detailSelection.minecraft || "") + " · " + (page.detailSelection.loader || "")
                            typographyRole: (true) ? "caption" : "body"
                            font.pixelSize: Style.value(page.appearance, "buildsPagePixelSize3")
                        }
                        UG.ScrollArea {
                            id: detailScroll
                            tag: "ui.scroll.buildspage.0"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 0
                            contentWidth: width
                            contentHeight: detailContent.implicitHeight
                            clip: true

                            ColumnLayout {
                                id: detailContent
                                width: detailScroll.width
                                spacing: Style.value(page.appearance, "buildsPageSpacing")
                                UG.ImageSurface {
                                    id: detailCover
                                    tag: "ui.pages.buildspage.15"
                                    objectName: "builds.details.cover"
                                    imageSource: page.detailSelection.background || ""
                                    imageKey: page.detailSelection.background ? "" : "assets/build-default.png"
                                    imageFit: Image.PreserveAspectCrop
                                    padding: 0
                                    clipContent: false
                                    displayText: ""
                                    useDisplayText: true
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: width
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: Style.value(page.appearance, "buildsPageLeftMargin")
                                    Layout.rightMargin: Style.value(page.appearance, "buildsPageRightMargin2")
                                    spacing: Style.value(page.appearance, "buildsPageSpacing2")
                                    BuildActions {
                                        objectName: "builds.details.play"
                                        Layout.fillWidth: true
                                        fillWidth: true
                                        buildId: page.detailSelection.id || ""
                                        running: !!page.detailSelection.running
                                    }
                                    UG.Button {
                                        tag: "ui.pages.buildspage.17"
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
                                            }["common.edit"] || ""] || ""
                                        Layout.fillWidth: true
                                        textKey: "common.edit"
                                        onClicked: Session.command("edit", page.detailSelection.id)
                                    }
                                    UG.Button {
                                        tag: "ui.pages.buildspage.18"
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
                                            }["common.delete"] || ""] || ""
                                        Layout.fillWidth: true
                                        textKey: "common.delete"
                                        enabled: !(page.detailSelection.running && Session.settings.safeMode)
                                        disabledExplanation: Session.text("builds.blocked.delete")
                                        onClicked: {
                                            deleteDialog.buildId = page.detailSelection.id
                                            deleteDialog.buildTitle = page.detailSelection.title
                                            deleteDialog.open()
                                        }
                                    }
                                    UG.Button {
                                        tag: "ui.pages.buildspage.19"
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
                                            }["builds.about"] || ""] || ""
                                        Layout.fillWidth: true
                                        textKey: "builds.about"
                                        objectName: "builds.about"
                                        onClicked: Session.command("about_build", page.detailSelection.id)
                                    }
                                }
                                UG.UiText {
                                    tag: "ui.pages.buildspage.16"
                                    verticalAlignment: Text.AlignVCenter
                                    Layout.fillWidth: true
                                    displayText: {
                                        Session.revision
                                        return page.detailSelection.description_key ? Session.summarizeDescription(Session.text(page.detailSelection.description_key), page.detailSelection.description_format || "md") : ""
                                    }
                                    maximumLineCount: Style.value(page.appearance, "buildsPageMaximumLineCount")
                                    typographyRole: (true) ? "caption" : "body"
                                    font.pixelSize: Style.value(page.appearance, "buildsPagePixelSize3")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    DeferredPopup {
        id: filters
        objectName: "builds.filter.loader"
        sceneSource: ThemeUI.viewUrl("dialogs/BuildsFilterPopup.qml")
        initialProperties: ({page: page})
    }
    DeferredPopup {
        id: createDialog
        objectName: "builds.create.loader"
        source: ThemeUI.viewUrl("dialogs/CreateBuildDialog.qml")
    }
    Dialogs.DeleteBuildDialog {
        id: deleteDialog
    }
    ContextMenu {
        id: buildMenu
        tag: "ui.build.context"
        property string buildId: ""
        readonly property var buildData: {
            Session.builds
            return Session.build(buildId)
        }
        readonly property var launchState: {
            Session.buildCoreRevision
            return Session.buildCoreState(buildId)
        }
        model: [
            {
                key: "play",
                text_key: buildData.running ? "common.close" : launchState.installed ? "builds.play" : "builds.install",
                icon: IconSources[buildData.running ? "stop" : launchState.installed ? "play" : "cores"] || "",
                state_key: buildData.running ? "danger" : launchState.pending_changes ? "warning" : "primary"
            },
            {
                key: "edit",
                text_key: "common.edit",
                icon: IconSources["edit"] || ""
            },
            {
                key: "delete",
                text_key: "common.delete",
                icon: IconSources["delete"] || "",
                enabled: !(buildData.running && Session.settings.safeMode),
                explanation: Session.text("builds.blocked.delete")
            },
            {
                key: "about",
                text_key: "builds.about",
                icon: IconSources["info"] || ""
            }
        ]
        onTriggered: key => {
            if (key === "delete") {
                deleteDialog.buildId = buildId
                deleteDialog.buildTitle = buildData.title
                deleteDialog.open()
            } else if (key === "about")
                Session.command("about_build", buildId)
            else if (key === "play") {
                if (buildData.running || !launchState.installed)
                    Session.command(buildData.running ? "close_client" : "install_build", buildId)
                else
                    contextLaunch.requestLaunch("")
            } else
                Session.command("edit", buildId)
        }
    }
    BuildActions {
        id: contextLaunch
        visible: false
        buildId: buildMenu.buildId
    }
}
