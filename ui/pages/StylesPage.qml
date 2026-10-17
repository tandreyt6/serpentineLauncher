import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import QtQuick.Dialogs
import Working.Gui as UG
import Launcher

UG.Page {
    id: page
    function handleShortcut(action) {
        if (action === "refresh" && !Session.styleCatalogueBusy) {
            Session.refreshAppearance("themes")
            return true
        }
        return false
    }
    tag: "ui.styles"
    objectName: "page.styles"
    property string expandedError: ""
    readonly property var entries: Session.styleCatalogue
    function buttonWidth(button, metrics) {
        return Math.max(button.appearance.controlWidth, Math.ceil(metrics.advanceWidth) + button.leftPadding + button.rightPadding + (button.iconSource.toString().length ? button.appearance.iconSize + button.appearance.iconGap : 0))
    }
    function revealInstalled() {
        const index = entries.findIndex(row => row.id === Session.styleSelection)
        if (index >= 0) {
            themes.currentIndex = index
            themes.positionViewAtIndex(index, ListView.Contain)
        }
    }
    Component.onCompleted: Qt.callLater(revealInstalled)
    Connections {
        target: Session
        function onStyleCatalogueChanged() { Qt.callLater(page.revealInstalled) }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: page.appearance.pageMargin
        spacing: page.appearance.rowGap
        RowLayout {
            Layout.fillWidth: true
            UG.UiText {
                tag: "styles.title"
                textKey: "nav.styles"
                typographyRole: "heading"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
            }
            LoadingIndicator {
                tag: "styles.loading"
                visible: Session.styleCatalogueBusy
                Layout.preferredWidth: page.appearance.iconSize
                Layout.preferredHeight: page.appearance.iconSize
            }
            UG.Button {
                id: refreshButton
                implicitWidth: page.buttonWidth(refreshButton, refreshMetrics)
                Layout.minimumWidth: implicitWidth
                TextMetrics {
                    id: refreshMetrics
                    text: refreshButton.text
                    font.family: refreshButton.appearance.fontFamily
                    font.pixelSize: refreshButton.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                tag: "styles.refresh"
                objectName: "styles.refresh"
                textKey: "common.refresh"
                iconSource: IconSources["refresh"]
                enabled: !Session.styleCatalogueBusy
                onActivated: Session.refreshAppearance("themes")
            }
            UG.Button {
                id: installButton
                implicitWidth: page.buttonWidth(installButton, installMetrics)
                Layout.minimumWidth: implicitWidth
                TextMetrics {
                    id: installMetrics
                    text: installButton.text
                    font.family: installButton.appearance.fontFamily
                    font.pixelSize: installButton.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                tag: "styles.install"
                objectName: "styles.install"
                stateKey: "primary"
                textKey: "styles.install"
                iconSource: IconSources["add"]
                enabled: !Session.styleCatalogueBusy
                onActivated: picker.open()
            }
        }
        UG.UiText {
            tag: "styles.drop.hint"
            textKey: "styles.drop_hint"
            typographyRole: "caption"
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        UG.Frame {
            tag: "styles.import.error"
            visible: Session.styleCatalogueError.length > 0
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: page.appearance.smallGap
                UG.UiText {
                    tag: "styles.import.error.heading"
                    textKey: "styles.install_failed"
                    color: page.appearance.danger
                    Layout.fillWidth: true
                }
                UG.UiText {
                    tag: "styles.import.error.details"
                    displayText: Session.styleCatalogueError
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }
        ListView {
            id: themes
            objectName: "styles.list"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: page.appearance.rowGap
            model: page.entries
            currentIndex: -1
            boundsBehavior: Flickable.StopAtBounds
            QC.ScrollBar.vertical: UG.ScrollBar { tag: "styles.scrollbar" }
            add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: page.appearance.surfaceDuration; easing.type: Easing.OutCubic } }
            displaced: Transition { NumberAnimation { properties: "x,y"; duration: page.appearance.surfaceDuration; easing.type: Easing.OutCubic } }
            delegate: UG.Frame {
                id: row
                required property var modelData
                required property int index
                objectName: "styles.row." + modelData.id
                tag: "styles.row"
                width: themes.width - page.appearance.scrollbarWidth
                height: implicitHeight
                readonly property bool activeStyle: Session.theme === modelData.id
                readonly property string themeFailure: ThemeUI.failedThemes[modelData.id] || ""
                readonly property string failure: themeFailure || modelData.error
                readonly property bool canChoose: !ThemeUI.busy && (!activeStyle || themeFailure.length > 0)
                function chooseTheme() {
                    if (canChoose)
                        ThemeUI.requestTheme(modelData.id)
                }
                stateKey: activeStyle ? "selected" : ""
                MouseArea {
                    parent: row
                    objectName: "styles.select." + row.modelData.id
                    anchors.fill: parent
                    z: 1
                    enabled: row.canChoose
                    cursorShape: Qt.PointingHandCursor
                    acceptedButtons: Qt.LeftButton
                    onClicked: row.chooseTheme()
                }
                contentItem: ColumnLayout {
                    z: 2
                    spacing: page.appearance.smallGap
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: page.appearance.layoutGap
                        Item {
                            Layout.preferredWidth: 2 * page.appearance.iconSize
                            Layout.preferredHeight: Layout.preferredWidth
                            Image {
                                anchors.fill: parent
                                source: row.modelData.icon
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                visible: source.toString().length > 0 && status !== Image.Error
                            }
                            UG.Icon {
                                tag: "styles.icon.placeholder"
                                anchors.centerIn: parent
                                width: page.appearance.iconSize
                                height: width
                                source: IconSources["styles"]
                                visible: !row.modelData.icon.length
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: page.appearance.smallGap
                            UG.UiText {
                                tag: "styles.row.title"
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                displayText: row.modelData.builtin ? Session.text("theme." + row.modelData.id) : row.modelData.title
                                font.weight: Font.DemiBold
                            }
                            UG.UiText {
                                tag: "styles.row.status"
                                Layout.fillWidth: true
                                typographyRole: "caption"
                                displayText: Session.text(row.themeFailure.length ? "styles.broken" : row.failure.length ? "styles.icon_error" : row.activeStyle ? "styles.current" : row.modelData.builtin ? "styles.builtin" : "styles.installed")
                                color: row.failure.length ? page.appearance.danger : page.appearance.muted
                            }
                        }
                        TaskErrorIndicator {
                            tag: "styles.row.error.indicator"
                            objectName: "styles.error." + row.modelData.id
                            errorIconSource: IconSources["theme-error"] || ""
                            visible: row.failure.length > 0
                            tooltip: row.failure
                            Accessible.name: Session.text("styles.broken")
                        }
                        UG.Button {
                            id: detailsButton
                            implicitWidth: page.buttonWidth(detailsButton, detailsMetrics)
                            Layout.minimumWidth: implicitWidth
                            TextMetrics {
                                id: detailsMetrics
                                text: detailsButton.text
                                font.family: detailsButton.appearance.fontFamily
                                font.pixelSize: detailsButton.appearance.fontSize
                                font.weight: Font.DemiBold
                            }
                            tag: "styles.row.error"
                            objectName: "styles.details." + row.modelData.id
                            visible: row.failure.length > 0
                            textKey: "styles.error_details"
                            onActivated: page.expandedError = page.expandedError === row.modelData.id ? "" : row.modelData.id
                        }
                        UG.Button {
                            id: chooseButton
                            implicitWidth: page.buttonWidth(chooseButton, chooseMetrics)
                            Layout.minimumWidth: implicitWidth
                            TextMetrics {
                                id: chooseMetrics
                                text: chooseButton.text
                                font.family: chooseButton.appearance.fontFamily
                                font.pixelSize: chooseButton.appearance.fontSize
                                font.weight: Font.DemiBold
                            }
                            tag: "styles.row.choose"
                            objectName: "styles.choose." + row.modelData.id
                            textKey: row.themeFailure.length ? "theme.retry" : row.activeStyle ? "styles.current" : "common.choose"
                            stateKey: row.themeFailure.length ? "danger" : row.activeStyle ? "selected" : "secondary"
                            enabled: row.canChoose
                            onActivated: row.chooseTheme()
                        }
                    }
                    UG.UiText {
                        tag: "styles.row.error.details"
                        visible: row.failure.length > 0 && page.expandedError === row.modelData.id
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        displayText: row.failure
                    }
                }
            }
        }
    }
    FileDialog {
        id: picker
        objectName: "styles.file.picker"
        title: Session.text("styles.install")
        fileMode: FileDialog.OpenFiles
        nameFilters: [Session.text("styles.file_filter")]
        onAccepted: Session.importThemes(selectedFiles.map(url => url.toString()))
    }
}
