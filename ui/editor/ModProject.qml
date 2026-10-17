import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T
import Working.Gui as UG
import Launcher

UG.Page {
    id: page
    tag: "editor.mod_project.page"
    objectName: "editor.mod.project.tab"
    required property string buildId
    required property string workspaceKey
    required property string projectId
    required property string tabKey
    property string contentKind: "mod"
    readonly property var project: Session.modProject(buildId, projectId, contentKind)
    readonly property var projectData: project ? project.data : ({})
    readonly property var releases: project ? project.versions : []
    readonly property string projectError: project ? project.error : ""
    readonly property bool projectBusy: project ? project.busy : false
    property string query: ""
    property string channel: ""
    function back() { Editors.command("return_mod_catalog", tabKey, workspaceKey) }
    function handleShortcut(action) {
        if (action === "find") {
            versionSearch.forceActiveFocus()
            versionSearch.selectAll()
        } else if (action === "refresh") {
            if (!projectBusy)
                project.reload()
        } else if (action === "back")
            back()
        else
            return false
        return true
    }
    Component.onCompleted: if (project) project.open()
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Style.value(page.appearance, "modProjectMargins")
        spacing: Style.value(page.appearance, "modProjectSpacing")
        RowLayout {
            Layout.fillWidth: true
            UG.Button {
                id: backButton
                tag: "editor.mod_project.back"
                objectName: "mod.project.back"
                textKey: "editor.mod_back"
                iconSource: IconSources.back || ""
                implicitWidth: Style.value(page.appearance, "modProjectImplicitWidth")
                onClicked: page.back()
            }
            UG.UiText { tag: "editor.mod_project.provider"; Layout.fillWidth: true; textKey: "common.provider.modrinth"; horizontalAlignment: Text.AlignRight }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Style.value(page.appearance, "modProjectSpacing2")
            Item {
                Layout.preferredWidth: Style.value(page.appearance, "modProjectPreferredWidth")
                Layout.preferredHeight: Style.value(page.appearance, "modProjectPreferredHeight")
                Image { anchors.fill: parent; source: page.projectData.icon || ""; sourceSize: Qt.size(Style.value(page.appearance, "modProjectSourceSize"), Style.value(page.appearance, "modProjectSourceSize")); asynchronous: true; fillMode: Image.PreserveAspectFit }
                UG.Icon { tag: "editor.mod_project.placeholder"; anchors.centerIn: parent; source: IconSources[page.contentKind === "shader" ? "shaders" : page.contentKind === "resourcepack" ? "resource-packs" : "mods"] || ""; visible: !page.projectData.icon }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.value(page.appearance, "modProjectSpacing3")
                UG.UiText { tag: "editor.mod_project.title"; Layout.fillWidth: true; displayText: page.projectData.title || page.projectId; typographyRole: "heading"; elide: Text.ElideRight }
                UG.UiText { tag: "editor.mod_project.summary"; Layout.fillWidth: true; displayText: page.projectData.description || ""; wrapMode: Text.Wrap; maximumLineCount: Style.value(page.appearance, "modProjectMaximumLineCount"); elide: Text.ElideRight }
            }
        }
        RowLayout {
            visible: !!page.projectError
            Layout.fillWidth: true
            UG.UiText { tag: "editor.mod_project.error"; Layout.fillWidth: true; displayText: page.projectError; wrapMode: Text.Wrap }
            UG.Button { tag: "editor.mod_project.retry"; textKey: "common.retry"; enabled: !!page.project && !page.projectBusy; onClicked: page.project.reload() }
        }
        UG.UiText { tag: "editor.mod_project.loading"; visible: page.projectBusy; textKey: "common.loading" }
        UG.SplitView {
            tag: "editor.mod_project.split"
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: width < 800 ? Qt.Vertical : Qt.Horizontal
            proportions: [0.38, 0.62]
            minimumSizes: orientation === Qt.Horizontal ? [220, 420] : [100, 260]
            UG.ScrollArea {
                id: description
                tag: "editor.mod_project.description_area"
                contentHeight: bodyText.height + 32
                UG.UiText {
                    id: bodyText
                    tag: "editor.mod_project.description"
                    objectName: "mod.project.description"
                    width: Math.max(Style.value(page.appearance, "modProjectWidth"), description.width - Style.value(page.appearance, "modProjectWidth2"))
                    x: 16
                    y: 16
                    displayText: Session.renderDescription(page.projectData.body || "", "md_html")
                    textFormat: Text.RichText
                    wrapMode: Text.Wrap
                }
            }
            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Style.value(page.appearance, "modProjectMargins2")
                    anchors.leftMargin: Style.value(page.appearance, "modProjectLeftMargin")
                    spacing: Style.value(page.appearance, "modProjectSpacing4")
                    UG.TextField {
                        id: versionSearch
                        tag: "editor.mod_project.search"
                        Layout.fillWidth: true
                        enabled: !!page.project
                        textKey: "editor.search_mod_version"
                        onTextEdited: { page.query = text; page.project.filterVersions(page.query, page.channel, page.project.minecraft, page.project.loader) }
                    }
                    ModFilters {
                        contentKind: page.contentKind
                        Layout.fillWidth: true
                        enabled: !!page.project
                        minecraft: page.project ? page.project.minecraft : ""
                        loader: page.project ? page.project.loader : ""
                        channel: page.channel
                        onApply: (minecraft, loader, category, sort, channel) => { page.channel = channel; page.project.filterVersions(page.query, channel, minecraft, loader) }
                    }
                    ListView {
                        id: versions
                        objectName: "mod.project.versions"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: Style.value(page.appearance, "modProjectSpacing")
                        reuseItems: true
                        cacheBuffer: 0
                        boundsBehavior: Flickable.StopAtBounds
                        model: page.releases
                        T.ScrollBar.vertical: UG.ScrollBar { tag: "editor.mod_project.versions.scrollbar" }
                        delegate: Component {
                            UG.Frame {
                                id: release
                                tag: "editor.mod_project.version"
                                required property var modelData
                                readonly property var releaseData: modelData || ({})
                                property bool expandedVersions: false
                                readonly property var supportedVersions: releaseData.minecraft || []
                                readonly property string selectedMinecraft: page && page.project ? page.project.minecraft : ""
                                readonly property var shownVersions: {
                                    if (expandedVersions) return supportedVersions
                                    const first = supportedVersions.slice(0, 5)
                                    if (selectedMinecraft && supportedVersions.includes(selectedMinecraft) && !first.includes(selectedMinecraft))
                                        return [selectedMinecraft].concat(first.slice(0, 4))
                                    return first
                                }
                                onModelDataChanged: expandedVersions = false
                                ListView.onReused: expandedVersions = false
                                readonly property bool queued: !!(page && page.project && page.project.queuedVersions.indexOf(releaseData.id) >= 0)
                                objectName: "mod.version." + releaseData.id
                                width: versions.width - versionsScrollbarWidth
                                readonly property real versionsScrollbarWidth: appearance.scrollbarWidth + appearance.spacing
                                height: releaseLayout.implicitHeight + topPadding + bottomPadding
                                padding: Style.value(page.appearance, "modProjectPadding")
                                ColumnLayout {
                                    id: releaseLayout
                                    anchors.fill: parent
                                    spacing: Style.value(page.appearance, "modProjectSpacing")
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: Style.value(page.appearance, "modProjectSpacing")
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            spacing: Style.value(page.appearance, "modProjectSpacing5")
                                            UG.UiText { tag: "editor.mod_project.version.name"; Layout.fillWidth: true; Layout.minimumWidth: 0; displayText: release.releaseData.number || ""; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                                            UG.UiText { tag: "editor.mod_project.version.meta"; Layout.fillWidth: true; Layout.minimumWidth: 0; displayText: (release.releaseData.channel || "") + " · " + (release.releaseData.published || "").slice(0, 10); wrapMode: Text.NoWrap; elide: Text.ElideRight }
                                        }
                                        UG.Button {
                                            id: enqueueButton
                                            tag: "editor.mod_project.version.enqueue"
                                            objectName: "mod.version.enqueue." + release.releaseData.id
                                            textKey: release.queued ? "editor.mod_queued" : "editor.add_to_queue"
                                            implicitWidth: enqueueMetrics.advanceWidth + appearance.controlPadding * 2
                                            TextMetrics { id: enqueueMetrics; text: enqueueButton.text; font.family: enqueueButton.appearance.fontFamily; font.pixelSize: enqueueButton.appearance.fontSize; font.weight: Font.DemiBold }
                                            enabled: !!(page && page.project && !release.queued && !page.project.pending && page.project.queue.state !== "downloading")
                                            onClicked: page.project.enqueue(release.releaseData.id, page.workspaceKey)
                                        }
                                    }
                                    UG.UiText {
                                        tag: "editor.mod_project.version.target"
                                        Layout.fillWidth: true
                                        displayText: (release.releaseData.loaders || []).join(", ")
                                        wrapMode: Text.NoWrap
                                        elide: Text.ElideRight
                                    }
                                    Flow {
                                        id: gameVersions
                                        Layout.fillWidth: true
                                        spacing: Style.value(page.appearance, "modProjectSpacing3")
                                        Repeater {
                                            model: release.shownVersions
                                            delegate: UG.Frame {
                                                id: gameBadge
                                                tag: "editor.mod_project.version.game"
                                                required property string modelData
                                                objectName: "mod.version.game." + release.releaseData.id + "." + modelData
                                                selected: modelData === release.selectedMinecraft
                                                stateKey: selected ? "selected" : ""
                                                padding: 0
                                                implicitWidth: gameText.implicitWidth + Style.value(page.appearance, "modProjectImplicitWidth2")
                                                implicitHeight: gameText.implicitHeight + Style.value(page.appearance, "modProjectImplicitHeight")
                                                UG.UiText {
                                                    id: gameText
                                                    tag: "editor.mod_project.version.game.text"
                                                    anchors.centerIn: parent
                                                    displayText: modelData
                                                    typographyRole: gameBadge.selected ? "body" : "caption"
                                                    font.weight: gameBadge.selected ? Font.DemiBold : Font.Normal
                                                    wrapMode: Text.NoWrap
                                                }
                                            }
                                        }
                                        UG.Button {
                                            id: moreVersions
                                            tag: "editor.mod_project.version.games.toggle"
                                            objectName: "mod.version.games.toggle." + release.releaseData.id
                                            visible: release.expandedVersions || release.supportedVersions.length > release.shownVersions.length
                                            useDisplayText: true
                                            displayText: release.expandedVersions ? Session.text("editor.supported_less") : Session.text("common.more") + " " + (release.supportedVersions.length - release.shownVersions.length)
                                            implicitWidth: moreMetrics.advanceWidth + appearance.controlPadding * 2
                                            implicitHeight: Style.value(page.appearance, "modProjectImplicitHeight2")
                                            TextMetrics { id: moreMetrics; text: moreVersions.text; font.family: moreVersions.appearance.fontFamily; font.pixelSize: moreVersions.appearance.fontSize; font.weight: Font.DemiBold }
                                            onClicked: release.expandedVersions = !release.expandedVersions
                                        }
                                    }
                                }
                            }
                        }
                    }
                    UG.UiText { tag: "editor.mod_project.empty"; visible: !!page.project && !versions.count && !page.projectBusy && !page.projectError; textKey: "editor.mod_versions_empty"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                }
            }
        }
    }
}
