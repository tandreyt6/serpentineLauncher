import QtQuick

Rectangle {
    id: visual
    required property QtObject viewState
    property real displayedPosition: viewState.position
    Behavior on displayedPosition {
        NumberAnimation {
            id: positionMotion
            duration: visual.viewState.reducedMotion || visual.viewState.suspended ? 0 : visual.viewState.smoothingDuration
            easing.type: visual.viewState.style.motionEasing
        }
    }
    Connections {
        target: visual.viewState
        function onReducedMotionChanged() { if (visual.viewState.reducedMotion) positionMotion.complete() }
        function onSuspendedChanged() { if (visual.viewState.suspended) positionMotion.complete() }
    }
    color: viewState.style.border
    radius: viewState.style.progressHeight / 2
    clip: true
    Rectangle {
        id: fill
        height: parent.height
        width: parent.width * (visual.viewState.indeterminate ? visual.viewState.style.busyFraction : visual.displayedPosition)
        radius: parent.radius
        color: visual.viewState.style.accent
        SequentialAnimation on x {
            running: visual.viewState.indeterminate && !visual.viewState.reducedMotion && !visual.viewState.suspended
            paused: running && visual.viewState.paused
            loops: Animation.Infinite
            NumberAnimation { from: 0; to: visual.width - fill.width; duration: visual.viewState.style.busyDuration; easing.type: visual.viewState.style.motionEasing }
            NumberAnimation { from: visual.width - fill.width; to: 0; duration: visual.viewState.style.busyDuration; easing.type: visual.viewState.style.motionEasing }
        }
    }
}
