import QtQuick
import Working.Gui as UG
import Launcher

Item {
    id: page
    property var pageContext: TabContext
    property bool mounted: false
    property bool loading: true
    LoadingIndicator {
        tag: "ui.editor.page.loading"
        objectName: "editor.page.loading." + page.pageContext.tabKey
        anchors.centerIn: parent
        visible: page.loading
    }
    Component.onCompleted: {
        mounted = true
        Editors.mountPage(page, pageContext.tabKey)
    }
}
