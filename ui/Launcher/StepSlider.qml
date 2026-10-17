import "Style.js" as Style
import QtQuick
import QtQuick.Controls as QC
import Working.Gui as UG

UG.Slider {
    id: control
    property int stepCount: UiDefaults.stepSliderStepCount
    property var initialValue: undefined
    property real trackThickness: Style.value(control.appearance, "stepSliderTrackThickness")
    property real handleDiameter: Style.value(control.appearance, "stepSliderHandleDiameter")
    property real tickDiameter: Style.value(control.appearance, "stepSliderTickDiameter")
    property bool showTicks: true
    property color trackColor: appearance.border
    property color fillColor: appearance.accent
    property color handleColor: Style.value(control.appearance, "stepSliderHandleColor")
    property color tickColor: appearance.foreground
    property real tickOpacity: Style.value(control.appearance, "stepSliderTickOpacity")
    property real disabledOpacity: Style.value(control.appearance, "stepSliderDisabledOpacity")
    property string tooltip: ""
    property int tooltipDelay: UiDefaults.stepSliderTooltipDelay
    property bool reducedMotion: false
    property int animationDuration: Style.value(control.appearance, "stepSliderAnimationDuration")
    property int dragAnimationDuration: Style.value(control.appearance, "stepSliderDragAnimationDuration")
    property int animationEasing: Easing.OutCubic
    property real hoverScale: Style.value(control.appearance, "stepSliderHoverScale")
    property real pressedScale: Style.value(control.appearance, "stepSliderPressedScale")
    readonly property int effectiveStepCount: Math.max(2, stepCount)
    readonly property real previewValue: from + position * (to - from)
    readonly property real animatedPosition: motion.position
    readonly property real maximumHandleDiameter: handleDiameter * Math.max(1, hoverScale, pressedScale)
    signal valueCommitted(real value)

    Item {
        id: motion
        visible: false
        property bool ready: false
        property real position: control.visualPosition
        Behavior on position {
            enabled: motion.ready && !control.reducedMotion && !control.suspended
            NumberAnimation {
                id: positionMotion
                duration: control.pressed ? control.dragAnimationDuration : control.animationDuration
                easing.type: control.animationEasing
            }
        }
    }
    Component.onCompleted: {
        if (typeof initialValue === "number" && isFinite(initialValue))
            value = initialValue
        if (positionMotion.running)
            positionMotion.complete()
        motion.position = Qt.binding(function () { return control.visualPosition })
        Qt.callLater(function () { if (motion) motion.ready = true })
    }
    onReducedMotionChanged: {
        if (reducedMotion && positionMotion.running)
            positionMotion.complete()
    }
    onSuspendedChanged: {
        if (suspended && positionMotion.running)
            positionMotion.complete()
    }

    from: 0
    to: from + effectiveStepCount - 1
    stepSize: Math.abs(to - from) / (effectiveStepCount - 1)
    snapMode: QC.Slider.SnapAlways
    live: false
    padding: maximumHandleDiameter / 2
    implicitHeight: vertical ? appearance.fieldWidth : Math.max(appearance.controlHeight, maximumHandleDiameter)
    implicitWidth: vertical ? Math.max(appearance.controlHeight, maximumHandleDiameter) : appearance.fieldWidth
    onMoved: {
        if (!pressed)
            valueCommitted(value)
    }
    onPressedChanged: {
        if (!pressed)
            valueCommitted(value)
    }
    QC.ToolTip.visible: enabled && (hovered || pressed) && tooltip.length > 0
    QC.ToolTip.text: tooltip
    QC.ToolTip.delay: tooltipDelay

    background: Item {
        opacity: control.enabled ? 1 : control.disabledOpacity
        Rectangle {
            id: track
            anchors.centerIn: parent
            width: control.vertical ? control.trackThickness : parent.width
            height: control.vertical ? parent.height : control.trackThickness
            radius: control.trackThickness / 2
            color: control.trackColor
            Rectangle {
                width: control.vertical ? parent.width : control.leftPadding + control.animatedPosition * control.availableWidth
                height: control.vertical ? parent.height - control.topPadding - control.animatedPosition * control.availableHeight : parent.height
                y: control.vertical ? parent.height - height : 0
                radius: parent.radius
                color: control.fillColor
            }
        }
        Repeater {
            model: control.showTicks ? control.effectiveStepCount : 0
            Rectangle {
                required property int index
                width: control.tickDiameter
                height: width
                radius: width / 2
                x: control.vertical ? (parent.width - width) / 2 : control.leftPadding + index * control.availableWidth / (control.effectiveStepCount - 1) - width / 2
                y: control.vertical ? control.topPadding + index * control.availableHeight / (control.effectiveStepCount - 1) - height / 2 : (parent.height - height) / 2
                color: control.tickColor
                opacity: control.tickOpacity
            }
        }
    }
    handle: Rectangle {
        width: control.handleDiameter
        height: width
        radius: width / 2
        x: control.vertical ? (control.width - width) / 2 : control.leftPadding + control.animatedPosition * control.availableWidth - width / 2
        y: control.vertical ? control.topPadding + control.animatedPosition * control.availableHeight - height / 2 : (control.height - height) / 2
        scale: !control.enabled ? 1 : control.pressed ? control.pressedScale : control.hovered ? control.hoverScale : 1
        Behavior on scale {
            NumberAnimation {
                duration: control.reducedMotion || control.suspended ? 0 : control.animationDuration
                easing.type: control.animationEasing
            }
        }
        color: control.handleColor
        opacity: control.enabled ? 1 : control.disabledOpacity
        border.color: control.appearance.focus
        border.width: control.visualFocus ? control.appearance.focusWidth : 0
    }
}
