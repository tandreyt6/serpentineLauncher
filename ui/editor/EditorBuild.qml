import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import QtQuick.Dialogs
import Working.Gui as UG
import Launcher
import Launcher.Native

UG.Page {
    id: buildEditor
    tag: "ui.page"
    required property string buildId
    required property string workspaceKey
    readonly property bool shortcutBoundary: true
    property string pendingShortcut: ""
    onSectionChanged: pendingShortcut = ""
    function sectionView() {
        return ({configs: configsSection, logs: logsSection, packs: packsSection, shaders: packsSection, files: filesSection, worlds: filesSection})[section]
    }
    function sectionLoaded(item) {
        finishUiLoading()
        const view = sectionView()
        if (!view || view.item !== item)
            return
        const action = pendingShortcut
        pendingShortcut = ""
        if (action.length && visible && enabled && Window.window && Window.window.active && !QC.Overlay.overlay.visible && item && item.visible && item.enabled && typeof item.handleShortcut === "function")
            item.handleShortcut(action)
    }
    function handleShortcut(action) {
        const view = sectionView()
        if (view && view.item && typeof view.item.handleShortcut === "function")
            return view.item.handleShortcut(action)
        if (view && view.status !== Loader.Error && (action === "find" || action === "refresh")) {
            pendingShortcut = action
            return true
        }
        if (action === "refresh" && section === "mods") {
            Session.command("editor_scan", buildId)
            return true
        }
        return false
    }
    property string section: Session.settings.editorDefaultSection === "mods" && buildData.loader === "Vanilla" ? "general" : Session.settings.editorDefaultSection
    property bool dirty: false
    property bool formDirty: false
    property string draftTitle: ""
    property string draftDescription: ""
    property string draftDescriptionFormat: "md"
    property string draftBackground: ""
    property string draftTitleColor: Session.defaultBuildTitleColor
    readonly property bool titleValid: draftTitle.trim().length > 0
    readonly property bool titleColorValid: /^#[0-9a-fA-F]{6}$/.test(draftTitleColor)
    property bool customJava: false
    property string draftJava: ""
    property string draftMinimum: ""
    property string draftMaximum: ""
    property string draftArgs: ""
    property string draftWidth: ""
    property string draftHeight: ""
    property bool draftFullscreen: false
    property bool saving: false
    property bool formReady: false
    property bool uiReady: false
    function finishUiLoading() { if (formReady) uiReady = true }
    property string draftMinecraft: ""
    property string draftLoader: "Vanilla"
    property string draftLoaderVersion: ""
    property var loaderOptions: []
    readonly property var loaderVersions: Session.live ? loaderOptions.map(option => option.value) : Session.loaderVersions(draftLoader, draftMinecraft)
    readonly property bool versionsBusy: (Session.catalogueUpdating, Session.versionCatalogueRevision, Session.catalogueBusy(draftLoader, draftMinecraft))
    readonly property bool coreSelectionValid: draftMinecraft.length > 0 && (draftLoader === "Vanilla" || loaderVersions.includes(draftLoaderVersion) || (draftMinecraft === buildData.minecraft && draftLoader === buildData.loader && draftLoaderVersion === buildData.loader_version && draftLoaderVersion.length > 0))
    readonly property var installedMods: Session.editorModsModel(buildId)
    readonly property var buildData: {
        Session.builds
        return Session.build(buildId)
    }
    readonly property bool protectedBuild: !!buildData.running && Session.settings.safeMode
    readonly property bool canSave: formDirty && !protectedBuild && !saving && coreSelectionValid && titleColorValid && titleValid
    onCanSaveChanged: {
        if (buildId && formReady)
            Editors.reportSaveState(buildId, canSave)
    }
    readonly property var modQueueModel: Session.contentQueue(buildId, "mod")
    onDraftDescriptionChanged: {
        if (descriptionDocument.text !== draftDescription)
            descriptionDocument.reset(buildId + ":description", draftDescription, 0)
    }
    UG.DocumentBuffer {
        id: descriptionDocument
        objectName: "editor.description.document." + buildEditor.buildId
        onChanged: {
            if (buildEditor.formReady && text !== buildEditor.draftDescription) {
                buildEditor.draftDescription = text
                buildEditor.markFormDirty()
            }
        }
    }
    function updateDirty() {
        dirty = formDirty
        Session.command("editor_dirty", buildId, dirty.toString())
    }
    function markFormDirty() {
        formDirty = true
        updateDirty()
    }
    function loadDecoration() {
        formReady = false
        loaderOptions = []
        draftTitle = buildData.title || ""
        draftDescription = buildData.description || (buildData.description_key ? Session.text(buildData.description_key) : "")
        draftDescriptionFormat = buildData.description_format || "md"
        draftBackground = buildData.background || ""
        draftTitleColor = buildData.title_color || Session.defaultBuildTitleColor
        draftJava = buildData.java_path || ""
        draftMinimum = buildData.memory_min ? buildData.memory_min.toString() : ""
        draftMaximum = buildData.memory_max ? buildData.memory_max.toString() : ""
        draftArgs = buildData.jvm_args || ""
        draftWidth = buildData.width ? buildData.width.toString() : ""
        draftHeight = buildData.height ? buildData.height.toString() : ""
        draftFullscreen = !!buildData.fullscreen
        customJava = !!(draftJava || draftMinimum || draftMaximum || draftArgs)
        draftMinecraft = buildData.minecraft || ""
        draftLoader = buildData.loader || "Vanilla"
        draftLoaderVersion = buildData.loader_version || ""
        formReady = true
        if (Session.live) {
            if (draftLoader !== "Vanilla" && draftMinecraft.length)
                Session.requestVersions(draftLoader, draftMinecraft)
        }
    }
    onDraftLoaderChanged: {
        if (formReady) {
            loaderOptions = []
            draftLoaderVersion = draftLoader === "Vanilla" ? "" : loaderVersions.length ? loaderVersions[0] : ""
            if (Session.live && draftLoader !== "Vanilla")
                Session.requestVersions(draftLoader, draftMinecraft)
        }
    }
    onDraftMinecraftChanged: {
        if (formReady) {
            loaderOptions = []
            draftLoaderVersion = draftLoader === "Vanilla" ? "" : loaderVersions.length ? loaderVersions[0] : ""
            if (Session.live && draftLoader !== "Vanilla")
                Session.requestVersions(draftLoader, draftMinecraft)
        }
    }
    function reconcileVersionSelection() {
        if (formReady && !versionsBusy && draftLoader !== "Vanilla" && !loaderVersions.includes(draftLoaderVersion) && !(draftMinecraft === buildData.minecraft && draftLoader === buildData.loader && draftLoaderVersion === buildData.loader_version && draftLoaderVersion.length > 0))
            draftLoaderVersion = loaderVersions.length ? loaderVersions[0] : ""
    }
    onLoaderVersionsChanged: reconcileVersionSelection()
    onVersionsBusyChanged: reconcileVersionSelection()
    readonly property bool coreSelectionChanged: draftMinecraft !== buildData.minecraft || draftLoader !== buildData.loader || draftLoaderVersion !== (buildData.loader_version || "")
    function save(confirmed = false) {
        if (!canSave)
            return
        if (coreSelectionChanged && !confirmed) {
            coreChangeDialog.open()
            return
        }
        saving = true
        if (!Session.saveBuild(buildId, draftTitle, draftDescription, draftBackground, draftDescriptionFormat, customJava ? draftJava : "", customJava ? draftMinimum : "", customJava ? draftMaximum : "", customJava ? draftArgs : "", draftWidth, draftHeight, draftFullscreen.toString(), draftMinecraft, draftLoader, draftLoaderVersion, draftTitleColor))
            saving = false
    }
    UG.ConfirmationDialog {
        id: coreChangeDialog
        tag: "ui.editor.core.change"
        objectName: "editor.core.change." + buildEditor.buildId
        heading: Session.text("editor.core_change_title")
        message: Session.text("editor.core_change_warning")
        actions: [
            { key: "cancel", text_key: "common.cancel" },
            { key: "continue", text_key: "common.confirm", state_key: "primary" }
        ]
        defaultAction: "cancel"
        cancelAction: "cancel"
        onActionRequested: action => {
            if (action === "continue")
                buildEditor.save(true)
        }
    }
    function discard() {
        loadDecoration()
        formDirty = false
        dirty = false
        Session.command("editor_dirty", buildId, "false")
    }
    Component.onCompleted: {
        objectName = "editor.build." + buildId
        loadDecoration()
        Editors.reportSaveState(buildId, canSave)
    }
    Connections {
        target: Session
        function onVersionsReady(loader, minecraft, choices) {
            if (loader === buildEditor.draftLoader && minecraft === buildEditor.draftMinecraft)
                buildEditor.loaderOptions = choices
        }
        function onCatalogueStateChanged() {
            if (buildEditor.formReady && Session.live && buildEditor.draftLoader !== "Vanilla")
                Session.requestVersions(buildEditor.draftLoader, buildEditor.draftMinecraft)
        }
        function onEditorSaveRequested(key) {
            if (key === buildEditor.buildId || key === "*")
                buildEditor.save()
        }
        function onEditorDiscardRequested(key) {
            if (key === buildEditor.buildId || key === "*")
                buildEditor.discard()
        }
        function onBuildSaved(key) {
            if (key === buildEditor.buildId) {
                buildEditor.saving = false
                buildEditor.formDirty = false
                buildEditor.dirty = false
                Session.command("editor_dirty", key, "false")
            }
        }
        function onNotice(message) {
            buildEditor.saving = false
        }
    }
    QtObject {
        id: backgroundPicker
        function open() { backgroundPickerLoader.active = true; backgroundPickerLoader.item.open() }
    }
    Loader {
        id: backgroundPickerLoader
        active: false
        sourceComponent: Component {
            FileDialog {
                nameFilters: ["Images (*.png *.jpg *.jpeg *.webp)"]
                onAccepted: {
                    buildEditor.draftBackground = selectedFile.toString()
                    buildEditor.markFormDirty()
                }
            }
        }
    }
    QtObject {
        id: titleColorPicker
        function open() { titleColorPickerLoader.active = true; titleColorPickerLoader.item.open() }
    }
    Loader {
        id: titleColorPickerLoader
        active: false
        sourceComponent: Component {
            ColorDialog {
                objectName: "editor.title.color.dialog"
                title: Session.text("editor.title_color")
                selectedColor: buildEditor.titleColorValid ? buildEditor.draftTitleColor : Session.defaultBuildTitleColor
                onAccepted: {
                    buildEditor.draftTitleColor = selectedColor.toString()
                    buildEditor.markFormDirty()
                }
            }
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: buildEditor.appearance.pageMargin
        spacing: buildEditor.appearance.rowGap
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Style.value(buildEditor.appearance, "editorBuildSpacing")
            ColumnLayout {
                Layout.preferredWidth: buildEditor.appearance.editorMenuWidth
                Layout.minimumWidth: buildEditor.appearance.editorMenuWidth
                Layout.maximumWidth: buildEditor.appearance.editorMenuWidth
                Layout.fillHeight: true
                spacing: Style.value(buildEditor.appearance, "editorBuildSpacing2")
                Repeater {
                    model: ["general", "java", "mods", "packs", "shaders", "configs", "files", "logs", "worlds"]
                    delegate: UG.Button {
                        tag: "ui.editor.editorbuild.3"
                        objectName: "editor.section." + buildEditor.buildId + "." + modelData
                        stateKey: (false) ? "primary" : "secondary"
                        required property string modelData
                        Layout.fillWidth: true
                        textKey: "editor." + modelData
                        iconSource: IconSources[({
                                    general: "settings",
                                    java: "java",
                                    mods: "mods",
                                    packs: "resource-packs",
                                    shaders: "shaders",
                                    configs: "config",
                                    files: "file",
                                    logs: "logs",
                                    worlds: "worlds"
                                })[modelData]] || ""
                        checked: buildEditor.section === modelData
                        enabled: modelData !== "mods" || buildEditor.buildData.loader !== "Vanilla"
                        onClicked: buildEditor.section = modelData
                    }
                }
                Item {
                    Layout.fillHeight: true
                }
            }
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                UG.AnimatedStack {
                    id: sectionStack
                    tag: "ui.editor.sections"
                    objectName: "editor.sections." + buildEditor.buildId
                    anchors.fill: parent
                    visible: ["general", "java", "mods"].includes(buildEditor.section)
                    retentionPolicy: "bounded"
                    maximumRetained: 3
                    currentKey: visible ? buildEditor.section : ""
                    pages: [
                        {
                            key: "general",
                            component: generalSection
                        },
                        {
                            key: "java",
                            component: javaSection
                        },
                        {
                            key: "mods",
                            component: modsSection
                        }
                    ]
                    Component {
                        id: generalSection
                        Loader {
                            asynchronous: true
                            onLoaded: buildEditor.finishUiLoading()
                            sourceComponent: Component {
                                EditorGeneral {
                                    editor: buildEditor
                                    descriptionBuffer: descriptionDocument
                                    onChooseCoverRequested: backgroundPicker.open()
                                    onChooseColorRequested: titleColorPicker.open()
                                }
                            }
                            LoadingIndicator {
                                tag: "ui.editor.general.loading"
                                anchors.centerIn: parent
                                visible: parent.status === Loader.Loading
                            }
                        }
                    }
                    Component {
                        id: javaSection
                        ColumnLayout {
                            Component.onCompleted: Qt.callLater(buildEditor.finishUiLoading)
                            spacing: Style.value(buildEditor.appearance, "editorBuildSpacing")
                            HoverHandler {
                                id: javaHover
                            }
                            QC.ToolTip.visible: buildEditor.protectedBuild && javaHover.hovered && visible
                            QC.ToolTip.text: Session.text("editor.blocked.java")
                            QC.ToolTip.delay: 600
                            UG.FormRow {
                                tag: "ui.editor.editorbuild.26"
                                Layout.fillWidth: true
                                textKey: "editor.custom"
                                UG.Switch {
                                    tag: "ui.editor.editorbuild.27"
                                    displayText: ""
                                    useDisplayText: true
                                    implicitWidth: Style.value(buildEditor.appearance, "editorBuildImplicitWidth")
                                    enabled: !buildEditor.protectedBuild && !buildEditor.saving
                                    checked: buildEditor.customJava
                                    onToggled: {
                                        buildEditor.customJava = checked
                                        buildEditor.markFormDirty()
                                    }
                                }
                            }
                            UG.UiText {
                                tag: "ui.editor.editorbuild.28"
                                verticalAlignment: Text.AlignVCenter
                                Layout.fillWidth: true
                                textKey: "editor.inherit"
                                visible: !buildEditor.customJava
                                typographyRole: (true) ? "caption" : "body"
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                visible: buildEditor.customJava
                                enabled: !buildEditor.protectedBuild && !buildEditor.saving
                                spacing: Style.value(buildEditor.appearance, "editorBuildSpacing3")
                                UG.UiText {
                                    tag: "ui.editor.editorbuild.29"
                                    verticalAlignment: Text.AlignVCenter
                                    textKey: "settings.java_path"
                                    typographyRole: (true) ? "caption" : "body"
                                }
                                UG.TextField {
                                    tag: "ui.editor.editorbuild.30"
                                    displayText: ""
                                    useDisplayText: true
                                    Layout.fillWidth: true
                                    text: buildEditor.draftJava
                                    placeholderText: Session.settings.javaPath || Session.text("editor.java_command_hint")
                                    onTextEdited: {
                                        buildEditor.draftJava = text
                                        buildEditor.markFormDirty()
                                    }
                                }
                                UG.UiText {
                                    tag: "ui.editor.editorbuild.31"
                                    verticalAlignment: Text.AlignVCenter
                                    textKey: "settings.memory_min"
                                    typographyRole: (true) ? "caption" : "body"
                                }
                                UG.TextField {
                                    tag: "ui.editor.editorbuild.32"
                                    displayText: ""
                                    useDisplayText: true
                                    Layout.fillWidth: true
                                    text: buildEditor.draftMinimum
                                    placeholderText: Session.settings.memoryMin
                                    onTextEdited: {
                                        buildEditor.draftMinimum = text
                                        buildEditor.markFormDirty()
                                    }
                                }
                                UG.UiText {
                                    tag: "ui.editor.editorbuild.33"
                                    verticalAlignment: Text.AlignVCenter
                                    textKey: "settings.memory_max"
                                    typographyRole: (true) ? "caption" : "body"
                                }
                                UG.TextField {
                                    tag: "ui.editor.editorbuild.34"
                                    displayText: ""
                                    useDisplayText: true
                                    Layout.fillWidth: true
                                    text: buildEditor.draftMaximum
                                    placeholderText: Session.settings.memoryMax
                                    onTextEdited: {
                                        buildEditor.draftMaximum = text
                                        buildEditor.markFormDirty()
                                    }
                                }
                                UG.UiText {
                                    tag: "ui.editor.editorbuild.35"
                                    verticalAlignment: Text.AlignVCenter
                                    textKey: "settings.jvm_args"
                                    typographyRole: (true) ? "caption" : "body"
                                }
                                UG.TextField {
                                    tag: "ui.editor.editorbuild.36"
                                    displayText: ""
                                    useDisplayText: true
                                    Layout.fillWidth: true
                                    text: buildEditor.draftArgs
                                    placeholderText: Session.settings.jvmArgs || Session.text("editor.jvm_args_hint")
                                    onTextEdited: {
                                        buildEditor.draftArgs = text
                                        buildEditor.markFormDirty()
                                    }
                                }
                            }
                            Item {
                                Layout.fillHeight: true
                            }
                        }
                    }
                    Component {
                        id: modsSection
                        ColumnLayout {
                            Component.onCompleted: Qt.callLater(buildEditor.finishUiLoading)
                            spacing: buildEditor.appearance.layoutGap
                            RowLayout {
                                Layout.fillWidth: true
                                UG.UiText {
                                    tag: "ui.editor.editorbuild.37"
                                    verticalAlignment: Text.AlignVCenter
                                    textKey: "editor.mod_queue"
                                    visible: buildEditor.modQueueModel.count > 0
                                }
                                UG.UiText {
                                    tag: "ui.editor.editorbuild.38"
                                    verticalAlignment: Text.AlignVCenter
                                    displayText: buildEditor.modQueueModel.count.toString()
                                    typographyRole: (true) ? "caption" : "body"
                                    visible: buildEditor.modQueueModel.count > 0
                                }
                                Item {
                                    Layout.fillWidth: true
                                }
                                OpenFolderButton {
                                    tag: "ui.editor.mods.folder"
                                    objectName: "editor.mods.folder"
                                    buildId: buildEditor.buildId
                                    directory: "mods"
                                    textKey: "editor.open_mods_folder"
                                }
                                UG.Button {
                                    id: button3
                                    implicitWidth: Math.max(Style.value(buildEditor.appearance, "editorBuildImplicitWidth2"), metrics3.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                    TextMetrics {
                                        id: metrics3
                                        text: button3.text
                                        font.family: button3.appearance.fontFamily
                                        font.pixelSize: button3.appearance.fontSize
                                        font.weight: Font.DemiBold
                                    }

                                    tag: "ui.editor.editorbuild.39"
                                    stateKey: (false) ? "primary" : "secondary"
                                    iconSource: IconSources[{
                                            "common.save": "save",
                                            "common.back": "back",
                                            "common.close": "close",
                                            "common.cards": "view-grid",
                                            "common.list": "view-list",
                                            "builds.new": "add",
                                            "builds.edit": "edit",
                                            "builds.delete": "delete",
                                            "builds.about": "info",
                                            "profile.add": "add",
                                            "editor.add_mod": "add",
                                            "common.edit": "edit",
                                            "common.delete": "delete",
                                            "common.refresh": "refresh",
                                            "common.add": "add"
                                        }["editor.add_mod"] || ""] || ""
                                    objectName: "editor.mods.add"
                                    textKey: "editor.mod_catalog"
                                    onClicked: Editors.command("open_mod_catalog", buildEditor.buildId, buildEditor.workspaceKey)
                                }
                                UG.Button {
                                    id: button4
                                    implicitWidth: Math.max(Style.value(buildEditor.appearance, "editorBuildImplicitWidth2"), metrics4.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                    TextMetrics {
                                        id: metrics4
                                        text: button4.text
                                        font.family: button4.appearance.fontFamily
                                        font.pixelSize: button4.appearance.fontSize
                                        font.weight: Font.DemiBold
                                    }

                                    tag: "ui.editor.editorbuild.40"
                                    stateKey: (true) ? "primary" : "secondary"
                                    iconSource: IconSources[{
                                            "common.save": "save",
                                            "common.back": "back",
                                            "common.close": "close",
                                            "common.cards": "view-grid",
                                            "common.list": "view-list",
                                            "builds.new": "add",
                                            "builds.edit": "edit",
                                            "builds.delete": "delete",
                                            "builds.about": "info",
                                            "profile.add": "add",
                                            "editor.add_mod": "add",
                                            "common.edit": "edit",
                                            "common.delete": "delete",
                                            "common.refresh": "refresh",
                                            "common.add": "add"
                                        }["editor.sync_mods"] || ""] || ""
                                    objectName: "editor.mods.sync"
                                    textKey: "editor.sync_mods"
                                    enabled: !buildEditor.protectedBuild && buildEditor.modQueueModel.count > 0 && !buildEditor.modQueueModel.syncing
                                    disabledExplanation: buildEditor.protectedBuild ? Session.text("editor.blocked.sync") : ""
                                    onClicked: Session.modBrowser(buildEditor.buildId, "mod").synchronize()
                                }
                            }
                            UG.ScrollArea {
                                id: modScroll
                                tag: "ui.scroll.editorbuild.1"
                                objectName: "editor.mods.scroll"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 0
                                clip: true
                                contentWidth: width

                                ColumnLayout {
                                    width: modScroll.width
                                    spacing: buildEditor.appearance.smallGap
                                    Repeater {
                                        model: Session.contentQueue(buildEditor.buildId, "mod")
                                        delegate: ContentQueueRow {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            entryData: modelData.detail
                                            protectedBuild: buildEditor.protectedBuild
                                            onRemoveRequested: key => Session.command("remove_queued_mod", buildEditor.buildId, key)
                                        }
                                    }
                                    Repeater {
                                        model: Session.downloadModel
                                        delegate: UG.OperationRow {
                                            tag: "ui.download.row"
                                            required property var modelData
                                            visible: modelData.kind === "mod" && modelData.owner_id === buildEditor.buildId
                                            Layout.fillWidth: true
                                            paused: modelData.paused
                                            stage: { Session.locale; return [Session.formatDownloadSpeed(modelData.bytes_per_second), modelData.stage].filter(Boolean).join(" · ") }
                                            objectName: "mod.download." + modelData.id
                                            displayText: modelData.title
                                            progress: (modelData.progress) / 100
                                            stageProgress: (modelData.stage_progress) / 100
                                            actionModel: [
                                                {
                                                    key: "pause",
                                                    icon: IconSources[(modelData.paused) ? "play" : "pause"] || "",
                                                    explanation: Session.text((modelData.paused) ? "downloads.resume" : "downloads.pause")
                                                },
                                                {
                                                    key: "cancel",
                                                    icon: IconSources["close"] || "",
                                                    explanation: Session.text("downloads.cancel")
                                                }
                                            ]
                                            onActionRequested: action => {
                                                if (action === "pause")
                                                    Session.command("pause_download", modelData.id)
                                                else
                                                    Session.command("cancel_download", modelData.id)
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: buildEditor.installedMods
                                        delegate: UG.Frame {
                                            tag: "ui.editor.editorbuild.44"
                                            objectName: "editor.mod." + modelData.path
                                            padding: 0
                                            displayText: ""
                                            useDisplayText: true

                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: buildEditor.appearance.editorModRowHeight
                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: Style.value(buildEditor.appearance, "editorBuildMargins")
                                                Image {
                                                    source: modelData.icon
                                                    Layout.preferredWidth: Style.value(buildEditor.appearance, "editorBuildPreferredWidth")
                                                    Layout.preferredHeight: Style.value(buildEditor.appearance, "editorBuildPreferredHeight")
                                                    fillMode: Image.PreserveAspectFit
                                                    visible: source.toString().length > 0
                                                }
                                                UG.UiText {
                                                    tag: "ui.editor.editorbuild.45"
                                                    verticalAlignment: Text.AlignVCenter
                                                    Layout.fillWidth: true
                                                    displayText: modelData.title
                                                    wrapMode: Text.NoWrap
                                                    elide: Text.ElideRight
                                                }
                                                UG.UiText {
                                                    tag: "ui.editor.editorbuild.46"
                                                    verticalAlignment: Text.AlignVCenter
                                                    displayText: modelData.version
                                                    typographyRole: (true) ? "caption" : "body"
                                                    font.pixelSize: Style.value(buildEditor.appearance, "editorBuildPixelSize")
                                                }
                                                UG.Switch {
                                                    tag: "ui.editor.editorbuild.47"
                                                    displayText: ""
                                                    useDisplayText: true
                                                    implicitWidth: Style.value(buildEditor.appearance, "editorBuildImplicitWidth")
                                                    checked: modelData.enabled
                                                    enabled: !buildEditor.protectedBuild
                                                    onToggled: Session.command("toggle_mod", buildEditor.buildId, modelData.path)
                                                }
                                                UG.Button {
                                                    id: button6
                                                    implicitWidth: Math.max(Style.value(buildEditor.appearance, "editorBuildImplicitWidth2"), metrics6.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                                    TextMetrics {
                                                        id: metrics6
                                                        text: button6.text
                                                        font.family: button6.appearance.fontFamily
                                                        font.pixelSize: button6.appearance.fontSize
                                                        font.weight: Font.DemiBold
                                                    }

                                                    tag: "ui.editor.editorbuild.48"
                                                    stateKey: (false) ? "primary" : "secondary"
                                                    displayText: ""
                                                    useDisplayText: true
                                                    iconSource: IconSources["delete"] || ""
                                                    width: Style.value(buildEditor.appearance, "editorBuildWidth")
                                                    enabled: !buildEditor.protectedBuild
                                                    onClicked: {
                                                        deleteFileDialog.path = modelData.path
                                                        deleteFileDialog.open()
                                                    }
                                                }
                                            }
                                            HoverHandler {
                                                id: modHover
                                            }
                                            QC.ToolTip.visible: buildEditor.protectedBuild && modHover.hovered
                                            QC.ToolTip.text: Session.text("editor.blocked.mods")
                                            QC.ToolTip.delay: 600
                                        }
                                    }
                                    UG.Frame {
                                        tag: "ui.editor.editorbuild.49"
                                        padding: 0
                                        displayText: ""
                                        useDisplayText: true
                                        stateKey: (drop.containsDrag) ? "selected" : ""

                                        Layout.fillWidth: true
                                        Layout.preferredHeight: buildEditor.appearance.modDropHeight

                                        UG.UiText {
                                            tag: "ui.editor.editorbuild.50"
                                            verticalAlignment: Text.AlignVCenter
                                            anchors.centerIn: parent
                                            textKey: "editor.drop"
                                            typographyRole: (true) ? "caption" : "body"
                                        }
                                        HoverHandler {
                                            id: dropHover
                                        }
                                        QC.ToolTip.visible: buildEditor.protectedBuild && dropHover.hovered
                                        QC.ToolTip.text: Session.text("editor.blocked.mods")
                                        QC.ToolTip.delay: 600
                                        DropArea {
                                            id: drop
                                            anchors.fill: parent
                                            enabled: buildEditor.visible && buildEditor.section === "mods" && Session.settings.modDrop && !buildEditor.protectedBuild
                                            onEntered: drag => {
                                                if (!drag.hasUrls || !drag.urls.every(url => url.toString().toLowerCase().endsWith(".jar")))
                                                    drag.accepted = false
                                            }
                                            onDropped: event => {
                                                event.acceptProposedAction()
                                                Session.dropMods(buildEditor.buildId, JSON.stringify(event.urls.map(url => url.toString())), buildEditor.workspaceKey)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Loader {
                    id: configsSection
                    anchors.fill: parent
                    visible: buildEditor.section === "configs"
                    onLoaded: buildEditor.sectionLoaded(item)
                    property bool loadedOnce: false
                    active: visible || loadedOnce
                    asynchronous: true
                    onVisibleChanged: if (visible) loadedOnce = true
                    Component.onCompleted: if (visible) loadedOnce = true
                    sourceComponent: Component {
                        ConfigExplorer {
                            buildId: buildEditor.buildId
                            onFileOpened: path => Editors.openFile(buildEditor.buildId, path, buildEditor.workspaceKey)
                        }
                    }
                }
                Loader {
                    id: logsSection
                    anchors.fill: parent
                    visible: buildEditor.section === "logs"
                    onLoaded: buildEditor.sectionLoaded(item)
                    property bool loadedOnce: false
                    active: visible || loadedOnce
                    asynchronous: true
                    onVisibleChanged: if (visible) loadedOnce = true
                    Component.onCompleted: if (visible) loadedOnce = true
                    sourceComponent: Component {
                        LogBrowser { buildId: buildEditor.buildId }
                    }
                }
                Loader {
                    id: packsSection
                    anchors.fill: parent
                    active: ["packs", "shaders"].includes(buildEditor.section)
                    onLoaded: buildEditor.sectionLoaded(item)
                    asynchronous: true
                    sourceComponent: Component {
                        PackLibrary {
                            buildId: buildEditor.buildId
                            workspaceKey: buildEditor.workspaceKey
                            contentKind: buildEditor.section === "shaders" ? "shader" : "resourcepack"
                            onDeleteRequested: path => { deleteFileDialog.path = path; deleteFileDialog.open() }
                            onImportRequested: directory => { collectionPicker.targetDirectory = directory; collectionPicker.open() }
                        }
                    }
                }
                Loader {
                    id: filesSection
                    anchors.fill: parent
                    visible: ["files", "worlds"].includes(buildEditor.section)
                    onLoaded: buildEditor.sectionLoaded(item)
                    property bool loadedOnce: false
                    active: visible || loadedOnce
                    asynchronous: true
                    onVisibleChanged: if (visible) loadedOnce = true
                    Component.onCompleted: if (visible) loadedOnce = true
                    sourceComponent: Component {
                        ConfigExplorer {
                            id: collectionExplorer
                            buildId: buildEditor.buildId
                            configOnly: false
                            rootDirectory: buildEditor.section === "worlds" ? "saves" : ""
                            folderTextKey: buildEditor.section === "worlds" ? "editor.open_worlds_folder" : "cores.open_folder"
                            editable: !buildEditor.protectedBuild
                            onFileOpened: path => Editors.openFile(buildEditor.buildId, path, buildEditor.workspaceKey)
                            onImportRequested: {
                                if (buildEditor.section === "worlds")
                                    worldPicker.open()
                                else {
                                    collectionPicker.targetDirectory = directory
                                    collectionPicker.open()
                                }
                            }
                            onDeleteRequested: path => {
                                deleteFileDialog.path = path
                                deleteFileDialog.open()
                            }
                        }
                    }
                }
            }
        }
    }
    QtObject {
        id: worldPicker
        function open() { worldPickerLoader.active = true; worldPickerLoader.item.open() }
    }
    Loader {
        id: worldPickerLoader
        active: false
        sourceComponent: Component {
            FolderDialog {
                onAccepted: Session.importFiles(buildEditor.buildId, "saves", JSON.stringify([selectedFolder.toString()]))
            }
        }
    }
    QtObject {
        id: collectionPicker
        property string targetDirectory: ""
        function open() { collectionPickerLoader.active = true; collectionPickerLoader.item.open() }
    }
    Loader {
        id: collectionPickerLoader
        active: false
        sourceComponent: Component {
            FileDialog {
                fileMode: FileDialog.OpenFiles
                onAccepted: Session.importFiles(buildEditor.buildId, collectionPicker.targetDirectory, JSON.stringify(selectedFiles.map(url => url.toString())))
            }
        }
    }
    UG.ConfirmationDialog {
        id: deleteFileDialog
        tag: "ui.editor.editorbuild.51"
        actions: [
            {
                key: "cancel",
                text_key: "common.cancel"
            },
            {
                key: "accept",
                text_key: "common.delete",
                state_key: "danger"
            }
        ]
        defaultAction: "accept"
        cancelAction: "cancel"
        property string path: ""
        heading: Session.text("files.delete_title")
        message: Session.text("files.delete_hint")
        detail: path
        onActionRequested: action => {
            if (action === "accept")
                Session.command("delete_file", buildEditor.buildId, path)
        }
    }
}
