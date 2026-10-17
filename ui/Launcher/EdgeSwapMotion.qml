import "Style.js" as Style
import QtQuick

QtObject {
    id: motion
    property string requestedSide: "left"
    property string displayedSide: "left"
    property bool animated: false
    property bool reducedMotion: false
    property bool suspended: false
    property int duration: Style.value(null, "edgeSwapMotionDuration")
    property real hiddenProgress: 0
    property bool ready: false
    readonly property bool running: swap.running
    function settle() {
        swap.stop()
        displayedSide = requestedSide
        hiddenProgress = 0
    }
    function updateSide() {
        if (!ready || !animated || reducedMotion || suspended || duration <= 0) {
            settle()
            return
        }
        if (displayedSide === requestedSide && !swap.running)
            return
        swap.stop()
        swap.start()
    }
    onRequestedSideChanged: updateSide()
    onAnimatedChanged: { if (!animated) settle() }
    onReducedMotionChanged: { if (reducedMotion) settle() }
    onSuspendedChanged: { if (suspended) settle() }
    onDurationChanged: { if (duration <= 0) settle() }
    Component.onCompleted: {
        settle()
        ready = true
    }
    property SequentialAnimation swap: SequentialAnimation {
        NumberAnimation {
            target: motion
            property: "hiddenProgress"
            to: 1
            duration: Math.max(0, motion.duration / 2)
            easing.type: Easing.InCubic
        }
        ScriptAction { script: motion.displayedSide = motion.requestedSide }
        NumberAnimation {
            target: motion
            property: "hiddenProgress"
            to: 0
            duration: Math.max(0, motion.duration / 2)
            easing.type: Easing.OutCubic
        }
    }
}
