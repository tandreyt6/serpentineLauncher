import QtQuick


Loader {
    id: loader
    active: false
    asynchronous: true
    property bool openingRequested: false
    property url sceneSource
    property var initialProperties: ({})
    readonly property bool popupVisible: item ? item.visible : false
    readonly property bool popupReady: status === Loader.Ready
    function open() {
        openingRequested = true
        if (!active && sceneSource.toString().length)
            setSource(sceneSource, initialProperties)
        active = true
        if (status === Loader.Ready) {
            openingRequested = false
            item.open()
        }
    }
    function close() {
        openingRequested = false
        if (item) item.close()
    }
    onLoaded: {
        if (openingRequested) {
            openingRequested = false
            item.open()
        }
    }
}
