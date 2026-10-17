import "Style.js" as Style
import QtQuick
import Working.Gui as UG

UG.NavigationPanel {
    id: panel
    tag: "ui.navigation"
    padding: horizontal ? 0 : Style.value(panel.appearance, "navigationPadding")
    property bool actionsEnabled: true
    property bool animateConfiguration: false
    property string requestedPlacement: "left"
    property string horizontalLabels: "text"
    readonly property bool horizontal: placement === "top" || placement === "bottom"
    readonly property bool showHorizontalLabels: horizontalLabels === "text"
    readonly property real horizontalContentWidth: buttonArea.horizontalContentWidth
    property bool motionReady: false
    readonly property bool configurationMotion: motionReady && animateConfiguration && !reducedMotion && !suspended && animationDuration > 0
    readonly property real edgeHiddenProgress: edgeSwap.hiddenProgress
    readonly property real collapsedButtonSide: Math.max(appearance.controlHeight, appearance.navigationCollapsedWidth - leftPadding - rightPadding)
    readonly property real collapsedPanelWidth: collapsedButtonSide + leftPadding + rightPadding
    readonly property int buttonMoveDuration: animationDuration <= 0 ? 0 : Math.max(Style.value(panel.appearance, "navigationButtonMoveDuration"), Math.round(animationDuration * Style.value(panel.appearance, "navigationButtonMoveDuration2")))
    implicitWidth: horizontal ? horizontalContentWidth : layoutMode === "push" ? panelWidth : collapsedPanelWidth
    placement: edgeSwap.displayedSide
    transform: Translate {
        x: panel.horizontal ? 0 : (panel.placement === "right" ? 1 : -1) * (panel.panelWidth + panel.appearance.navigationCollapsedWidth) * edgeSwap.hiddenProgress
        y: panel.horizontal ? (panel.placement === "bottom" ? 1 : -1) * panel.height * edgeSwap.hiddenProgress : 0
    }
    background.visible: !horizontal
    background.width: horizontal ? width : panelWidth
    background.x: placement === "right" ? width - panelWidth : 0
    EdgeSwapMotion {
        id: edgeSwap
        requestedSide: panel.requestedPlacement
        animated: panel.animateConfiguration
        reducedMotion: panel.reducedMotion
        suspended: panel.suspended
        duration: panel.animationDuration
    }
    Component.onCompleted: Qt.callLater(function () { if (panel) panel.motionReady = true })
    signal contextRequested(var owner, real x, real y)
    property int hoverCloseDelay: UiDefaults.navigationHoverCloseDelay
    property bool hoverRetained: false
    readonly property bool hoverRevealEnabled: !horizontal && (revealMode === "hover" || revealMode === "hover+button")
    readonly property bool delayedExpanded: expanded || hoverRevealEnabled && hoverRetained
    panelWidth: horizontal ? width : delayedExpanded ? Math.max(appearance.navigationExpandedWidth, collapsedPanelWidth) : collapsedPanelWidth
    onHorizontalChanged: resetHoverRetention()
    function resetHoverRetention() {
        if (hoverCloseTimer)
            hoverCloseTimer.stop()
        hoverRetained = false
    }
    onRevealModeChanged: {
        resetHoverRetention()
        if (hoverRevealEnabled && panelHover && panelHover.hovered)
            hoverRetained = true
    }
    onVisibleChanged: {
        if (!visible)
            resetHoverRetention()
    }
    onSuspendedChanged: {
        if (suspended)
            resetHoverRetention()
    }
    HoverHandler {
        id: panelHover
        parent: panel.contentItem
        enabled: panel.hoverRevealEnabled && panel.visible && !panel.suspended
        onHoveredChanged: {
            if (hovered) {
                hoverCloseTimer.stop()
                panel.hoverRetained = true
            } else if (panel.hoverRetained && enabled) {
                hoverCloseTimer.restart()
            } else {
                panel.resetHoverRetention()
            }
        }
    }
    Timer {
        id: hoverCloseTimer
        interval: Math.max(0, panel.hoverCloseDelay)
        repeat: false
        onTriggered: {
            if (!panelHover.hovered)
                panel.hoverRetained = false
        }
    }
    MouseArea {
        id: inputShield
        parent: panel
        objectName: "navigation.inputShield"
        x: panel.placement === "right" ? panel.width - width : 0
        width: panel.horizontal ? panel.width : panel.panelWidth
        height: panel.height
        acceptedButtons: Qt.AllButtons
        onWheel: wheel => wheel.accepted = true
        onClicked: mouse => {
            if (mouse.button === Qt.RightButton && panel.actionsEnabled)
                panel.contextRequested(inputShield, mouse.x, mouse.y)
        }
    }
    MouseArea {
        parent: panel.contentItem
        anchors.fill: parent
        z: 10
        acceptedButtons: Qt.RightButton
        enabled: panel.actionsEnabled
        onClicked: mouse => panel.contextRequested(panel.contentItem, mouse.x, mouse.y)
    }
    contentItem: Item {
        id: buttonArea
        z: 1
        property int layoutRevision: 0
        readonly property real buttonGap: Style.value(panel.appearance, "navigationButtonGap")
        readonly property real horizontalButtonHeight: Math.min(panel.appearance.controlHeight, height)
        readonly property real horizontalContentWidth: {
            layoutRevision
            if (!panel.horizontal)
                return 0
            let total = Math.max(0, entries.count - 1) * buttonGap
            for (let i = 0; i < entries.count; ++i) {
                const button = entries.itemAt(i)
                if (button)
                    total += button.width
            }
            return total
        }
        readonly property real rowHeight: panel.collapsedButtonSide
        readonly property real rowStep: rowHeight + buttonGap
        readonly property real groupHeight: entries.count * rowHeight + Math.max(0, entries.count - 1) * buttonGap
        readonly property real headerHeight: toggle.visible ? toggle.height + buttonGap : 0
        readonly property real groupStart: headerHeight + (panel.alignment === "center" ? Math.max(0, (height - headerHeight - groupHeight) / 2) : 0)
        implicitHeight: headerHeight + groupHeight
        width: Math.max(0, (panel.horizontal ? panel.width : panel.panelWidth) - panel.leftPadding - panel.rightPadding)
        x: (!panel.horizontal && panel.placement === "right" ? panel.width - panel.panelWidth : 0) + panel.leftPadding
        Flickable {
            id: horizontalScroll
            objectName: "navigation.horizontal.scroll"
            anchors.fill: parent
            visible: panel.horizontal
            clip: true
            contentWidth: buttonArea.horizontalContentWidth
            contentHeight: height
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentWidth > width
            onContentWidthChanged: contentX = Math.max(0, Math.min(contentX, contentWidth - width))
            onWidthChanged: contentX = Math.max(0, Math.min(contentX, contentWidth - width))
            WheelHandler {
                target: null
                enabled: panel.horizontal && horizontalScroll.interactive
                onWheel: event => {
                    const delta = event.pixelDelta.x || event.pixelDelta.y || (event.angleDelta.x || event.angleDelta.y) / 120 * Style.value(panel.appearance, "navigationWheelStep")
                    horizontalScroll.contentX = Math.max(0, Math.min(horizontalScroll.contentWidth - horizontalScroll.width, horizontalScroll.contentX - delta))
                    event.accepted = true
                }
            }
        }
        UG.NavigationButton {
            id: toggle
            objectName: "navigation.toggle"
            tag: "ui.navigation.toggle"
            textKey: "nav.toggle"
            navigationIcon: IconSources["menu"] || ""
            stateKey: "secondary"
            padding: 0
            labelPolicy: "clip"
            iconSize: appearance.navigationIconSize
            iconInset: (buttonArea.rowHeight - iconSize) / 2
            textInset: Math.max(buttonArea.rowHeight, Style.value(panel.appearance, "navigationTextInset"))
            iconTint: appearance.foreground
            labelColor: appearance.foreground
            labelWidth: appearance.navigationExpandedWidth - textInset - Style.value(panel.appearance, "navigationLabelWidth")
            tooltipKey: panel.actionsEnabled ? "nav.toggle" : ""
            expanded: false
            enabled: panel.actionsEnabled
            visible: !panel.horizontal && (panel.revealMode === "button" || panel.revealMode === "hover+button")
            width: buttonArea.rowHeight
            height: buttonArea.rowHeight
            onActivated: panel.opened = !panel.opened
        }
        Repeater {
            id: entries
            parent: panel.horizontal ? horizontalScroll.contentItem : buttonArea
            model: panel.model
            onItemAdded: buttonArea.layoutRevision += 1
            onItemRemoved: buttonArea.layoutRevision += 1
            delegate: UG.NavigationButton {
                id: entryButton
                required property int index
                required property var modelData
                tag: "ui.navigation.entry"
                key: modelData.key
                textKey: modelData.text_key
                navigationIcon: IconSources[modelData.icon] || ""
                stateKey: selected ? "selected" : "secondary"
                padding: 0
                labelPolicy: panel.horizontal ? "fade" : "clip"
                iconSize: appearance.navigationIconSize
                iconInset: panel.horizontal ? panel.showHorizontalLabels ? Style.value(panel.appearance, "navigationHorizontalPadding") : (width - iconSize) / 2 : (buttonArea.rowHeight - iconSize) / 2
                textInset: panel.horizontal ? Style.value(panel.appearance, "navigationHorizontalPadding") + iconSize + appearance.iconGap : Math.max(buttonArea.rowHeight, Style.value(panel.appearance, "navigationTextInset"))
                iconTint: selected ? appearance.accent : appearance.foreground
                labelColor: appearance.foreground
                labelWidth: appearance.navigationExpandedWidth - textInset - Style.value(panel.appearance, "navigationLabelWidth")
                tooltipKey: panel.actionsEnabled && !expanded ? modelData.text_key : ""
                expanded: panel.horizontal ? panel.showHorizontalLabels : panel.delayedExpanded
                selected: panel.selectedKey === modelData.key
                enabled: panel.actionsEnabled
                width: panel.horizontal ? panel.showHorizontalLabels ? Math.ceil(labelMetrics.advanceWidth) + iconSize + appearance.iconGap + 2 * Style.value(panel.appearance, "navigationHorizontalPadding") : buttonArea.horizontalButtonHeight : buttonArea.width
                height: panel.horizontal ? buttonArea.horizontalButtonHeight : buttonArea.rowHeight
                TextMetrics {
                    id: labelMetrics
                    text: entryButton.text
                    font.family: entryButton.appearance.fontFamily
                    font.pixelSize: entryButton.appearance.fontSize
                }
                Behavior on width {
                    enabled: panel.horizontal && panel.motionReady && panel.edgeHiddenProgress === 0
                    NumberAnimation { duration: panel.reducedMotion || panel.suspended ? 0 : panel.buttonMoveDuration; easing.type: Easing.InOutCubic }
                }
                readonly property real targetX: {
                    buttonArea.layoutRevision
                    if (!panel.horizontal)
                        return 0
                    let offset = index * buttonArea.buttonGap
                    for (let i = 0; i < index; ++i) {
                        const previous = entries.itemAt(i)
                        if (previous)
                            offset += previous.width
                    }
                    return offset
                }
                readonly property real targetY: panel.horizontal ? (buttonArea.height - height) / 2 : buttonArea.groupStart + index * buttonArea.rowStep
                property bool rowReady: false
                readonly property int staggerIndex: panel.alignment === "center" ? entries.count - 1 - index : index
                function placeRow() {
                    if (!rowReady)
                        return
                    rowMotion.stop()
                    x = targetX
                    if (!panel.horizontal && panel.edgeHiddenProgress === 0 && panel.configurationMotion && Math.abs(y - targetY) > 0.01)
                        rowMotion.start()
                    else
                        y = targetY
                }
                onTargetYChanged: placeRow()
                onTargetXChanged: placeRow()
                onActiveFocusChanged: {
                    if (activeFocus && panel.horizontal)
                        horizontalScroll.contentX = Math.max(0, Math.min(horizontalScroll.contentWidth - horizontalScroll.width, Math.min(x, Math.max(horizontalScroll.contentX, x + width - horizontalScroll.width))))
                }
                Component.onCompleted: {
                    x = targetX
                    y = targetY
                    rowReady = true
                }
                property SequentialAnimation rowMotion: SequentialAnimation {
                    PauseAnimation { duration: Math.min(Math.max(0, entryButton.staggerIndex), Style.value(panel.appearance, "navigationDuration")) * Style.value(panel.appearance, "navigationDuration2") }
                    NumberAnimation {
                        target: entryButton
                        property: "y"
                        to: entryButton.targetY
                        duration: panel.buttonMoveDuration
                        easing.type: Easing.InOutCubic
                    }
                }
                Connections {
                    target: panel
                    function onConfigurationMotionChanged() {
                        if (!panel.configurationMotion) {
                            entryButton.placeRow()
                        }
                    }
                }
                objectName: "nav." + modelData.key
                onActivated: panel.pageRequested(modelData.key)
            }
        }
    }
}
