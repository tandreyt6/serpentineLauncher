import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher

UG.Widget {
    id: entry
    tag: "ui.build.entry"
    padding: 0
    property bool cardsMode: true
    property bool large: false
    property Item collectionViewport: null
    property int geometryAnimationDuration: Style.value(entry.appearance, "buildEntryGeometryAnimationDuration")
    property bool geometryReady: false
    readonly property string geometryKey: String(collectionContext.key || "")
    readonly property bool geometryMotionEnabled: geometryReady && cardsMode && collectionViewport !== null && !reducedMotion && !suspended
    readonly property point slotPosition: {
        if (!collectionViewport)
            return Qt.point(0, 0)
        let item = entry
        let x = 0
        let y = 0

        while (item && item !== collectionViewport.contentItem) {
            x += item.x
            y += item.y
            item = item.parent
        }
        return item ? Qt.point(x, y) : Qt.point(0, 0)
    }
    function prepareGeometry() {
        geometryReady = false
        Qt.callLater(resetGeometry)
    }
    function resetGeometry() {
        updateGeometry()
        geometryReady = true
    }
    function scheduleGeometry() {
        Qt.callLater(updateGeometry)
    }
    function updateGeometry() {


        if (collectionViewport)
            collectionViewport.forceLayout()
        const destination = slotPosition
        if (cardGeometry.targetX === destination.x && cardGeometry.targetY === destination.y
                && cardGeometry.targetWidth === width && cardGeometry.targetHeight === height) {
            if (!geometryMotionEnabled && geometryMotion.running)
                geometryMotion.complete()
            return
        }
        const currentX = cardGeometry.shownX
        const currentY = cardGeometry.shownY
        const currentWidth = cardGeometry.shownWidth
        const currentHeight = cardGeometry.shownHeight
        geometryMotion.stop()
        cardGeometry.startX = currentX
        cardGeometry.startY = currentY
        cardGeometry.startWidth = currentWidth
        cardGeometry.startHeight = currentHeight
        cardGeometry.targetX = destination.x
        cardGeometry.targetY = destination.y
        cardGeometry.targetWidth = width
        cardGeometry.targetHeight = height
        cardGeometry.progress = geometryMotionEnabled ? 0 : 1
        if (geometryMotionEnabled)
            geometryMotion.start()
    }
    onSlotPositionChanged: scheduleGeometry()
    onWidthChanged: scheduleGeometry()
    onHeightChanged: scheduleGeometry()
    onGeometryKeyChanged: prepareGeometry()
    onCardsModeChanged: prepareGeometry()
    onReducedMotionChanged: {
        if (reducedMotion)
            prepareGeometry()
    }
    onSuspendedChanged: {
        if (suspended)
            prepareGeometry()
    }
    Component.onCompleted: prepareGeometry()
    readonly property var buildData: {
        Session.builds
        return Session.build(collectionContext.key)
    }
    signal selectedBuild(string key)
    signal doubleClickedBuild(string key)
    signal contextRequested(string key, var owner, real x, real y)
    function requestPlay() {
        if (cardsMode && entryContent.item)
            entryContent.item.requestPlay()
    }
    Item {
        id: cardGeometry
        visible: false
        property real progress: 1
        property real targetX: 0
        property real targetY: 0
        property real targetWidth: 0
        property real targetHeight: 0
        property real startX: 0
        property real startY: 0
        property real startWidth: 0
        property real startHeight: 0
        readonly property real shownX: startX + (targetX - startX) * progress
        readonly property real shownY: startY + (targetY - startY) * progress
        readonly property real shownWidth: startWidth + (targetWidth - startWidth) * progress
        readonly property real shownHeight: startHeight + (targetHeight - startHeight) * progress
        NumberAnimation on progress {
            id: geometryMotion
            running: false
            to: 1
            duration: entry.geometryAnimationDuration
            easing.type: Easing.OutCubic
        }
    }
    contentItem: Item {
        implicitWidth: entryContent.implicitWidth
        implicitHeight: entryContent.implicitHeight
        Loader {
            id: entryContent
            x: entry.cardsMode ? cardGeometry.shownX - entry.slotPosition.x : 0
            y: entry.cardsMode ? cardGeometry.shownY - entry.slotPosition.y : 0
            width: entry.cardsMode ? cardGeometry.shownWidth : parent.width
            height: entry.cardsMode ? cardGeometry.shownHeight : parent.height
            sourceComponent: entry.cardsMode ? card : row
        }
    }


    MouseArea {
        parent: entryContent.item
        width: parent ? parent.selectionWidth : 0
        height: parent ? parent.selectionHeight : 0
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.RightButton)
                entry.contextRequested(entry.buildData.id, entryContent.item, mouse.x, mouse.y)
            else
                entry.selectedBuild(entry.buildData.id)
        }
        onDoubleClicked: mouse => {
            if (mouse.button === Qt.LeftButton && entry.cardsMode) {
                mouse.accepted = true
                entry.doubleClickedBuild(entry.buildData.id)
            }
        }
    }
    Component {
        id: card
        UG.Card {
            id: buildCard
            function requestPlay() { cardActions.requestPlay() }
            readonly property real selectionWidth: width
            readonly property var cardAppearance: appearance || ({})
            property bool keyboardReveal: false
            readonly property bool revealActions: selected || cardHover.hovered || keyboardReveal
            function releaseKeyboardReveal() {
                if (!activeFocus && !cardActions.activeFocus)
                    keyboardReveal = false
            }
            onFocusReasonChanged: {
                if (focusReason === Qt.TabFocusReason || focusReason === Qt.BacktabFocusReason || focusReason === Qt.ShortcutFocusReason)
                    keyboardReveal = true
                else if (focusReason === Qt.MouseFocusReason)
                    keyboardReveal = false
            }
            onActiveFocusChanged: Qt.callLater(releaseKeyboardReveal)
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)
                    keyboardReveal = true
            }
            property real revealProgress: revealActions ? 1 : 0
            readonly property real selectionHeight: revealActions ? Math.max(0, height - cardActions.height - 12) : height
            Behavior on revealProgress {
                NumberAnimation {
                    duration: Session.settings.reducedMotion ? 0 : buildCard.cardAppearance.duration || 0
                    easing.type: Easing.OutQuad
                }
            }
            tag: "ui.build.card"
            objectName: "build.card." + entry.buildData.id
            key: entry.buildData.id || ""
            displayText: entry.buildData.title || ""
            selected: Session.selectedId === key
            stateKey: selected ? "selected" : ""
            imageLayout: "background"
            imageSource: entry.buildData.background || ""
            imageKey: entry.buildData.background ? "" : "assets/build-default.png"
            imageFit: Image.PreserveAspectCrop
            padding: 0
            clipContent: false
            focusPolicy: Qt.TabFocus
            onSelectedRequested: key => entry.selectedBuild(key)
            onContextRequested: (key, x, y) => entry.contextRequested(key, buildCard, x, y)
            contentItem: Item {
                clip: true
                Connections {
                    target: cardActions
                    function onActiveFocusChanged() { Qt.callLater(buildCard.releaseKeyboardReveal) }
                }
                HoverHandler {
                    id: cardHover
                    parent: buildCard
                    onHoveredChanged: {
                        if (hovered)
                            buildCard.keyboardReveal = false
                    }
                }
                UG.Frame {
                    tag: "ui.build.badge"
                    objectName: "build.loader." + entry.buildData.id
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.margins: Style.value(entry.appearance, "buildEntryMargins")
                    width: Math.min(loaderLabel.implicitWidth + Style.value(entry.appearance, "buildEntryWidth"), (parent.width - Style.value(entry.appearance, "buildEntryWidth2")) / 2)
                    height: loaderLabel.implicitHeight + Style.value(entry.appearance, "buildEntryHeight")
                    padding: Style.value(entry.appearance, "buildEntryPadding")
                    topPadding: Style.value(entry.appearance, "buildEntryTopPadding")
                    bottomPadding: Style.value(entry.appearance, "buildEntryBottomPadding")
                    displayText: ""
                    useDisplayText: true
                    tooltip: loaderLabel.truncated ? entry.buildData.loader || "" : ""
                    contentItem: UG.UiText {
                        id: loaderLabel
                        tag: "ui.build.badge.text"
                        objectName: "build.loader.text." + entry.buildData.id
                        displayText: entry.buildData.loader || ""
                        typographyRole: "caption"
                        wrapMode: Text.NoWrap
                        elide: Text.ElideRight
                    }
                }
                UG.Frame {
                    tag: "ui.build.badge"
                    objectName: "build.version." + entry.buildData.id
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Style.value(entry.appearance, "buildEntryMargins")
                    width: Math.min(versionLabel.implicitWidth + Style.value(entry.appearance, "buildEntryWidth"), (parent.width - Style.value(entry.appearance, "buildEntryWidth2")) / 2)
                    height: versionLabel.implicitHeight + Style.value(entry.appearance, "buildEntryHeight")
                    padding: Style.value(entry.appearance, "buildEntryPadding")
                    topPadding: Style.value(entry.appearance, "buildEntryTopPadding")
                    bottomPadding: Style.value(entry.appearance, "buildEntryBottomPadding")
                    displayText: ""
                    useDisplayText: true
                    tooltip: versionLabel.truncated ? entry.buildData.minecraft || "" : ""
                    contentItem: UG.UiText {
                        id: versionLabel
                        tag: "ui.build.badge.text"
                        objectName: "build.version.text." + entry.buildData.id
                        displayText: entry.buildData.minecraft || ""
                        typographyRole: "caption"
                        wrapMode: Text.NoWrap
                        elide: Text.ElideRight
                    }
                }
                Rectangle {
                    objectName: "build.titleShade." + entry.buildData.id
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: Math.min(parent.height, Style.value(entry.appearance, "buildEntryHeight2"))
                    bottomLeftRadius: buildCard.cardAppearance.radius || 0
                    bottomRightRadius: buildCard.cardAppearance.radius || 0
                    gradient: Gradient {
                        GradientStop { position: 0; color: Style.value(entry.appearance, "buildPassiveShadowStart") }
                        GradientStop { position: Style.value(entry.appearance, "buildEntryPosition"); color: Style.value(entry.appearance, "buildPassiveShadowMiddle") }
                        GradientStop { position: 1; color: Style.value(entry.appearance, "buildPassiveShadowEnd") }
                    }
                }
                Rectangle {
                    objectName: "build.shade." + entry.buildData.id
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: Math.min(parent.height, Style.value(entry.appearance, "buildEntryHeight3"))
                    bottomLeftRadius: buildCard.cardAppearance.radius || 0
                    bottomRightRadius: buildCard.cardAppearance.radius || 0
                    opacity: buildCard.revealProgress
                    gradient: Gradient {
                        GradientStop { position: 0; color: Style.value(entry.appearance, "buildPassiveShadowStart") }
                        GradientStop { position: Style.value(entry.appearance, "buildEntryPosition2"); color: Style.value(entry.appearance, "buildActiveShadowMiddle") }
                        GradientStop { position: 1; color: Style.value(entry.appearance, "buildActiveShadowEnd") }
                    }
                }
                UG.UiText {
                    tag: "ui.build.card.title"
                    objectName: "build.title." + entry.buildData.id
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: Style.value(entry.appearance, "buildEntryLeftMargin")
                    anchors.rightMargin: Style.value(entry.appearance, "buildEntryRightMargin")
                    anchors.bottomMargin: Style.value(entry.appearance, "buildEntryBottomMargin") + buildCard.revealProgress * (cardActions.height + Style.value(entry.appearance, "buildEntryBottomMargin2"))
                    displayText: entry.buildData.title || ""
                    color: entry.buildData.title_color || Session.defaultBuildTitleColor
                    style: Text.Outline
                    styleColor: Style.value(entry.appearance, "buildTitleOutlineColor")
                    wrapMode: Text.NoWrap
                    elide: Text.ElideRight
                    font.pixelSize: Style.value(entry.appearance, "buildEntryPixelSize")
                }
                BuildActions {
                    id: cardActions
                    objectName: "build.play." + entry.buildData.id
                    x: 10
                    y: parent.height - height - 10 + (1 - buildCard.revealProgress) * (height + 10)
                    width: parent.width - Style.value(entry.appearance, "buildEntryWidth3")
                    opacity: buildCard.revealProgress
                    visible: buildCard.revealProgress > 0
                    enabled: buildCard.revealActions
                    buildId: entry.buildData.id || ""
                    running: !!entry.buildData.running
                    fillWidth: true
                }
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    radius: buildCard.cardAppearance.radius || 0
                    border.width: buildCard.cardAppearance.borderWidth || 0
                    border.color: buildCard.cardAppearance.accent || "transparent"
                    visible: buildCard.selected
                }
            }
        }
    }
    Component {
        id: row
        UG.Frame {
            id: line
            property bool keyboardReveal: false
            readonly property bool revealActions: selected || rowHover.hovered || keyboardReveal
            function releaseKeyboardReveal() {
                if (!activeFocus && !rowActions.activeFocus)
                    keyboardReveal = false
            }
            focusPolicy: Qt.TabFocus
            onFocusReasonChanged: {
                if (focusReason === Qt.TabFocusReason || focusReason === Qt.BacktabFocusReason || focusReason === Qt.ShortcutFocusReason)
                    keyboardReveal = true
                else if (focusReason === Qt.MouseFocusReason)
                    keyboardReveal = false
            }
            onActiveFocusChanged: Qt.callLater(releaseKeyboardReveal)
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)
                    keyboardReveal = true
            }
            readonly property real selectionWidth: revealActions ? Math.max(0, width - rightPadding - rowActions.width - rowContent.spacing) : width
            readonly property real selectionHeight: height
            tag: "ui.build.row"
            objectName: "build.row." + entry.buildData.id
            selected: Session.selectedId === entry.buildData.id
            stateKey: selected ? "selected" : ""
            padding: Style.value(entry.appearance, "buildEntryPadding2")
            displayText: ""
            useDisplayText: true
            contentItem: RowLayout {
                id: rowContent
                spacing: Style.value(entry.appearance, "buildEntrySpacing")
                HoverHandler {
                    id: rowHover
                    parent: line
                    onHoveredChanged: {
                        if (hovered)
                            line.keyboardReveal = false
                    }
                }
                Connections {
                    target: rowActions
                    function onActiveFocusChanged() { Qt.callLater(line.releaseKeyboardReveal) }
                }
                UG.ImageSurface {
                    tag: "ui.build.row.cover"
                    padding: 0
                    imageSource: entry.buildData.background || ""
                    imageKey: entry.buildData.background ? "" : "assets/build-default.png"
                    Layout.preferredWidth: Style.value(entry.appearance, "buildEntryPreferredWidth")
                    Layout.fillHeight: true
                    displayText: ""
                    useDisplayText: true
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    UG.UiText {
                        tag: "ui.build.row.title"
                        displayText: entry.buildData.title || ""
                        Layout.fillWidth: true
                        wrapMode: Text.NoWrap
                        elide: Text.ElideRight
                    }
                    UG.UiText {
                        tag: "ui.build.row.version"
                        displayText: (entry.buildData.minecraft || "") + " · " + (entry.buildData.loader || "")
                        typographyRole: "caption"
                    }
                }
                BuildActions {
                    id: rowActions
                    opacity: line.revealActions ? 1 : 0
                    enabled: line.revealActions
                    Behavior on opacity {
                        NumberAnimation {
                            duration: Session.settings.reducedMotion ? 0 : line.appearance.duration
                            easing.type: Easing.OutQuad
                        }
                    }
                    buildId: entry.buildData.id || ""
                    running: !!entry.buildData.running
                }
            }
        }
    }
}
