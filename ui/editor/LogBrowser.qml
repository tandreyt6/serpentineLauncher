import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher.Native
import Launcher

Item {
    id: browser
    property string buildId: ""
    property bool rawMode: false
    function handleShortcut(action) {
        if (action === "find")
            findBar.open()
        else if (action === "refresh")
            Session.command("editor_scan", buildId)
        else
            return false
        return true
    }
    readonly property var records: {
        Session.editorRevision
        return Session.live ? Session.editorLogs(buildId) : Editors.logs()
    }
    readonly property var dates: Array.from(new Set(records.map(log => log.date))).sort().reverse()
    property string selectedDate: dates.length ? dates[0] : ""
    readonly property var files: records.filter(log => log.date === selectedDate)
    property string selectedFile: files.length ? files[0].name : ""
    readonly property int dateIndex: dates.indexOf(selectedDate)
    readonly property string selectedText: {
        const log = files.find(file => file.name === selectedFile)
        return log ? (rawMode ? log.text : log.formatted_text) : ""
    }
    onSelectedTextChanged: viewer.document.reset(selectedFile, selectedText, 0)
    onDatesChanged: {
        if (!dates.includes(selectedDate))
            selectedDate = dates.length ? dates[0] : ""
    }
    onFilesChanged: selectedFile = files.length ? files[0].name : ""
    objectName: "editor.logs"
    ColumnLayout {
        anchors.fill: parent
        spacing: Style.value((browser.Window.window ? browser.Window.window.appearance : null), "logBrowserSpacing")
        RowLayout {
            Layout.fillWidth: true
            UG.ComboBox {
                id: viewMode
                tag: "ui.logs.mode"
                objectName: "logs.mode"
                implicitWidth: Math.max(appearance.controlWidth, modeMetrics.advanceWidth + 2 * appearance.controlPadding + appearance.iconSize + appearance.iconGap)
                Layout.minimumWidth: implicitWidth
                topPadding: Math.max(0, (height - Math.ceil(modeMetrics.height)) / 2)
                bottomPadding: topPadding
                model: [
                    { key: "formatted", text: Session.text("logs.formatted") },
                    { key: "raw", text: Session.text("logs.raw") }
                ]
                selectedKey: browser.rawMode ? "raw" : "formatted"
                Accessible.name: Session.text("logs.view_mode")
                onSelectionRequested: key => browser.rawMode = key === "raw"
                TextMetrics {
                    id: modeMetrics
                    text: Session.text("logs.formatted")
                    font.family: viewMode.appearance.fontFamily
                    font.pixelSize: viewMode.appearance.fontSize
                    font.weight: Font.DemiBold
                }
            }
            Item { Layout.fillWidth: true }
            OpenFolderButton {
                tag: "ui.logs.folder"
                objectName: "editor.logs.folder"
                buildId: browser.buildId
                directory: "logs"
                textKey: "editor.open_logs_folder"
            }
        }
        RowLayout {
            Layout.fillWidth: true
            UG.ToolButton {
                tag: "ui.logs.previous"
                stateKey: "secondary"
                displayText: ""
                useDisplayText: true
                Layout.preferredWidth: implicitHeight
                Layout.maximumWidth: implicitHeight
                iconSource: IconSources["back"] || ""
                Accessible.name: Session.text("logs.previous")
                tooltipKey: "logs.previous"
                enabled: browser.dateIndex < browser.dates.length - 1
                onActivated: browser.selectedDate = browser.dates[browser.dateIndex + 1]
            }
            UG.ComboBox {
                id: selection0
                density: "compact"
                tag: "ui.logs.date"
                objectName: "logs.date"
                Layout.preferredWidth: Style.value((browser.Window.window ? browser.Window.window.appearance : null), "logBrowserPreferredWidth")
                searchable: true
                model: {
                    const options = (function () {
                            return browser.dates.map(date => ({
                                        key: date,
                                        text: date
                                    }))
                        })()
                    return options.map(option => ({
                                key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                text: option.label === undefined ? option.text : option.label,
                                secondary: option.note || option.secondary || "",
                                pinned: !!option.pinned,
                                enabled: option.enabled !== false
                            }))
                }
                selectedKey: (browser.selectedDate) || "__all__"
                onSelectionRequested: selected => {
                    const key = selected === "__all__" ? "" : selected
                    browser.selectedDate = key
                }
            }
            UG.ToolButton {
                tag: "ui.logs.calendar"
                Layout.preferredWidth: implicitHeight
                Layout.maximumWidth: implicitHeight
                stateKey: "secondary"
                displayText: ""
                useDisplayText: true
                iconSource: IconSources["calendar"] || ""
                Accessible.name: Session.text("logs.calendar")
                tooltipKey: "logs.calendar"
                onActivated: calendar.open()
            }
            UG.ToolButton {
                tag: "ui.logs.next"
                stateKey: "secondary"
                displayText: ""
                useDisplayText: true
                Layout.preferredWidth: implicitHeight
                Layout.maximumWidth: implicitHeight
                iconKey: "assets/next.png"
                Accessible.name: Session.text("logs.next")
                tooltipKey: "logs.next"
                enabled: browser.dateIndex > 0
                onActivated: browser.selectedDate = browser.dates[browser.dateIndex - 1]
            }
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value((browser.Window.window ? browser.Window.window.appearance : null), "logBrowserImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }
                tag: "ui.logs.refresh"
                stateKey: "secondary"
                textKey: "common.refresh"
                onActivated: Session.command("editor_scan", browser.buildId)
            }
            UG.ComboBox {
                id: selection1
                density: "compact"
                tag: "ui.logs.file"
                objectName: "logs.file"
                Layout.fillWidth: true
                searchable: true
                model: {
                    const options = (function () {
                            return browser.files.map(log => ({
                                        key: log.name,
                                        text: log.name
                                    }))
                        })()
                    return options.map(option => ({
                                key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                text: option.label === undefined ? option.text : option.label,
                                secondary: option.note || option.secondary || "",
                                pinned: !!option.pinned,
                                enabled: option.enabled !== false
                            }))
                }
                selectedKey: (browser.selectedFile) || "__all__"
                onSelectionRequested: selected => {
                    const key = selected === "__all__" ? "" : selected
                    browser.selectedFile = key
                }
            }
        }
        TextFindBar {
            id: findBar
            targetEditor: viewer
            Layout.fillWidth: true
        }
        UG.TextViewer {
            id: viewer
            tag: "ui.logs.viewer"
            objectName: "logs.text"
            Layout.fillWidth: true
            Layout.fillHeight: true
            wrap: Session.settings.logWrap
            followTail: Session.settings.logFollowTail
            Component.onCompleted: document.reset(browser.selectedFile, browser.selectedText, 0)
            LogHighlighter {
                document: viewer.document.document
                colors: [viewer.appearance.muted, viewer.appearance.accent, viewer.appearance.foreground, Style.value(viewer.appearance, "logWarning"), viewer.appearance.danger]
            }
        }
    }
    UG.PopupPanel {
        id: calendar
        tag: "ui.logs.calendar.popup"
        width: Style.value((browser.Window.window ? browser.Window.window.appearance : null), "logBrowserWidth")
        height: Style.value((browser.Window.window ? browser.Window.window.appearance : null), "logBrowserHeight")
        contentItem: UG.DatePicker {
            tag: "ui.logs.calendar.days"
            selectedDate: browser.selectedDate
            availableDates: browser.dates
            onDateRequested: date => {
                browser.selectedDate = date
                calendar.close()
            }
        }
    }
}
