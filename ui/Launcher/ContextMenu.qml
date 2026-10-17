import QtQuick
import Working.Gui as UG

UG.Menu {
    id: control
    function selectionView() {
        return contentItem && contentItem.item ? contentItem.item : contentItem
    }
    function resetSelection() {
        const view = selectionView()
        if (view && view.currentIndex !== undefined)
            view.currentIndex = -1
    }
    onAboutToShow: resetSelection()
    onOpened: {
        resetSelection()
        const view = selectionView()
        if (view)
            view.forceActiveFocus()
    }
    onClosed: Qt.callLater(resetSelection)
    Connections {
        target: control.contentItem
        ignoreUnknownSignals: true
        function onLoaded() { control.resetSelection() }
    }
}
