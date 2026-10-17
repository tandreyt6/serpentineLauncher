import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

UG.ScrollArea {
    id: general
    tag: "ui.editor.general.scroll"
    objectName: "editor.general"
    required property var editor
    required property var descriptionBuffer
    property bool descriptionPreview: false
    readonly property bool editable: !editor.protectedBuild && !editor.saving
    readonly property string selectionState: [editor.draftMinecraft, editor.draftLoader, editor.draftLoaderVersion, editor.draftDescriptionFormat].join("|")
    onSelectionStateChanged: Qt.callLater(syncSelections)
    function syncSelections() {
        minecraftChoice.selectedKey = editor.draftMinecraft || "__all__"
        loaderChoice.selectedKey = editor.draftLoader
        loaderVersionChoice.selectedKey = editor.draftLoaderVersion || "__all__"
        formatChoice.selectedKey = editor.draftDescriptionFormat
    }
    Component.onCompleted: Qt.callLater(syncSelections)
    signal chooseCoverRequested()
    signal chooseColorRequested()
    contentWidth: width
    contentHeight: sections.height + 12

    ColumnLayout {
        id: sections
        x: 4
        width: Math.max(0, general.width - Style.value(general.appearance, "editorGeneralWidth"))
        spacing: Style.value(general.appearance, "editorGeneralSpacing")

        UG.Frame {
            tag: "ui.editor.general.appearance"
            Layout.fillWidth: true
            padding: Style.value(general.appearance, "editorGeneralPadding")
            contentItem: ColumnLayout {
                spacing: Style.value(general.appearance, "editorGeneralSpacing")
                UG.UiText {
                    tag: "ui.editor.general.appearance.heading"
                    textKey: "editor.decor"
                    font.weight: Font.DemiBold
                }
                GridLayout {
                    id: appearanceLayout
                    Layout.fillWidth: true
                    columns: width >= 600 ? 2 : 1
                    columnSpacing: Style.value(general.appearance, "editorGeneralColumnSpacing")
                    rowSpacing: Style.value(general.appearance, "editorGeneralRowSpacing")
                    ColumnLayout {
                        Layout.preferredWidth: Style.value(general.appearance, "editorGeneralPreferredWidth")
                        Layout.maximumWidth: Style.value(general.appearance, "editorGeneralMaximumWidth")
                        Layout.alignment: Qt.AlignTop | Qt.AlignHCenter
                        spacing: Style.value(general.appearance, "editorGeneralSpacing2")
                        UG.ImageSurface {
                            id: cardPreview
                            tag: "ui.editor.general.cover"
                            objectName: "editor.cover.preview"
                            Layout.fillWidth: true
                            Layout.preferredHeight: width
                            imageSource: general.editor.draftBackground
                            imageKey: general.editor.draftBackground ? "" : "assets/build-default.png"
                            imageFit: Image.PreserveAspectCrop
                            padding: 0
                            clipContent: true
                            contentItem: Item {
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: Math.min(parent.height, Style.value(general.appearance, "editorGeneralHeight"))
                                    gradient: Gradient {
                                        GradientStop { position: 0; color: Style.value(general.appearance, "buildPassiveShadowStart") }
                                        GradientStop { position: Style.value(general.appearance, "editorGeneralPosition"); color: Style.value(general.appearance, "buildPassiveShadowMiddle") }
                                        GradientStop { position: 1; color: Style.value(general.appearance, "buildPassiveShadowEnd") }
                                    }
                                }
                                UG.Frame {
                                    tag: "ui.build.badge"
                                    x: 8; y: 8
                                    width: Math.min(loaderBadge.implicitWidth + Style.value(general.appearance, "editorGeneralWidth2"), parent.width / 2 - Style.value(general.appearance, "editorGeneralWidth2"))
                                    height: loaderBadge.implicitHeight + Style.value(general.appearance, "editorGeneralHeight2")
                                    padding: Style.value(general.appearance, "editorGeneralPadding2"); topPadding: Style.value(general.appearance, "editorGeneralTopPadding"); bottomPadding: Style.value(general.appearance, "editorGeneralBottomPadding")
                                    contentItem: UG.UiText {
                                        id: loaderBadge
                                        tag: "ui.build.badge.text"
                                        displayText: general.editor.draftLoader
                                        typographyRole: "caption"
                                        elide: Text.ElideRight
                                    }
                                }
                                UG.Frame {
                                    tag: "ui.build.badge"
                                    anchors.right: parent.right
                                    anchors.rightMargin: Style.value(general.appearance, "editorGeneralRightMargin")
                                    y: 8
                                    width: Math.min(versionBadge.implicitWidth + Style.value(general.appearance, "editorGeneralWidth2"), parent.width / 2 - Style.value(general.appearance, "editorGeneralWidth2"))
                                    height: versionBadge.implicitHeight + Style.value(general.appearance, "editorGeneralHeight2")
                                    padding: Style.value(general.appearance, "editorGeneralPadding2"); topPadding: Style.value(general.appearance, "editorGeneralTopPadding"); bottomPadding: Style.value(general.appearance, "editorGeneralBottomPadding")
                                    contentItem: UG.UiText {
                                        id: versionBadge
                                        tag: "ui.build.badge.text"
                                        displayText: general.editor.draftMinecraft
                                        typographyRole: "caption"
                                        elide: Text.ElideRight
                                    }
                                }
                                UG.UiText {
                                    tag: "ui.build.card.title"
                                    objectName: "editor.cover.title"
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    anchors.margins: Style.value(general.appearance, "editorGeneralMargins")
                                    displayText: general.editor.draftTitle.trim() || Session.text("builds.title")
                                    color: general.editor.titleColorValid ? general.editor.draftTitleColor : Session.defaultBuildTitleColor
                                    font.pixelSize: Style.value(general.appearance, "editorGeneralPixelSize")
                                    style: Text.Outline
                                    styleColor: Style.value(general.appearance, "buildTitleOutlineColor")
                                    wrapMode: Text.NoWrap
                                    elide: Text.ElideRight
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Style.value(general.appearance, "editorGeneralSpacing2")
                            UG.Button {
                                tag: "ui.editor.general.cover.choose"
                                objectName: "editor.cover.choose"
                                Layout.fillWidth: true
                                implicitWidth: Style.value(general.appearance, "editorGeneralImplicitWidth")
                                textKey: "common.choose"
                                enabled: general.editable
                                onClicked: general.chooseCoverRequested()
                            }
                            UG.Button {
                                tag: "ui.editor.general.cover.reset"
                                objectName: "editor.cover.reset"
                                Layout.fillWidth: true
                                implicitWidth: Style.value(general.appearance, "editorGeneralImplicitWidth2")
                                textKey: "common.reset"
                                enabled: general.editable && general.editor.draftBackground.length > 0
                                onClicked: {
                                    general.editor.draftBackground = ""
                                    general.editor.markFormDirty()
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.alignment: Qt.AlignTop
                        spacing: Style.value(general.appearance, "editorGeneralSpacing2")
                        UG.UiText { tag: "ui.editor.general.title.label"; textKey: "builds.title" }
                        UG.TextField {
                            tag: "ui.editor.general.title"
                            displayText: ""
                            useDisplayText: true
                            objectName: "editor.title"
                            Layout.fillWidth: true
                            text: general.editor.draftTitle
                            enabled: general.editable
                            onTextEdited: { general.editor.draftTitle = text; general.editor.markFormDirty() }
                        }
                        UG.UiText {
                            tag: "ui.editor.general.title.validation"
                            textKey: "validation.title"
                            visible: !general.editor.titleValid
                            color: appearance.danger
                        }
                        UG.UiText { tag: "ui.editor.general.id.label"; textKey: "builds.id"; Layout.topMargin: Style.value(general.appearance, "editorGeneralTopMargin") }
                        UG.TextField {
                            tag: "ui.editor.general.id"
                            displayText: ""
                            useDisplayText: true
                            objectName: "editor.build.id"
                            Layout.fillWidth: true
                            text: general.editor.buildId
                            readOnly: true
                        }
                        UG.UiText { tag: "ui.editor.general.color.label"; textKey: "editor.title_color"; Layout.topMargin: Style.value(general.appearance, "editorGeneralTopMargin") }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Style.value(general.appearance, "editorGeneralSpacing2")
                            UG.UiText {
                                tag: "ui.editor.general.color.sample"
                                textKey: "editor.color_sample"
                                color: general.editor.titleColorValid ? general.editor.draftTitleColor : Session.defaultBuildTitleColor
                                font.pixelSize: Style.value(general.appearance, "editorGeneralPixelSize2")
                                style: Text.Outline
                                styleColor: Style.value(general.appearance, "buildTitleOutlineColor")
                            }
                            UG.TextField {
                                tag: "ui.editor.general.color"
                                displayText: Session.defaultBuildTitleColor
                                useDisplayText: true
                                objectName: "editor.title.color"
                                Layout.fillWidth: true
                                Layout.minimumWidth: Style.value(general.appearance, "editorGeneralMinimumWidth")
                                placeholderText: Session.defaultBuildTitleColor
                                text: general.editor.draftTitleColor
                                enabled: general.editable
                                onTextEdited: { general.editor.draftTitleColor = text; general.editor.markFormDirty() }
                            }
                            UG.Button {
                                tag: "ui.editor.general.color.choose"
                                implicitWidth: Style.value(general.appearance, "editorGeneralImplicitWidth")
                                textKey: "common.choose"
                                enabled: general.editable
                                onClicked: general.chooseColorRequested()
                            }
                            UG.Button {
                                tag: "ui.editor.general.color.reset"
                                objectName: "editor.title.color.reset"
                                implicitWidth: Style.value(general.appearance, "editorGeneralImplicitWidth2")
                                textKey: "common.reset"
                                enabled: general.editable && general.editor.draftTitleColor.toLowerCase() !== Session.defaultBuildTitleColor
                                onClicked: { general.editor.draftTitleColor = Session.defaultBuildTitleColor; general.editor.markFormDirty() }
                            }
                        }
                        UG.UiText {
                            tag: "ui.editor.general.color.validation"
                            textKey: "editor.title_color_hint"
                            color: appearance.danger
                            visible: !general.editor.titleColorValid
                        }
                    }
                }
            }
        }

        UG.Frame {
            tag: "ui.editor.general.core"
            Layout.fillWidth: true
            padding: Style.value(general.appearance, "editorGeneralPadding")
            contentItem: ColumnLayout {
                spacing: Style.value(general.appearance, "editorGeneralSpacing3")
                UG.UiText { tag: "ui.editor.general.core.heading"; textKey: "editor.core_settings"; font.weight: Font.DemiBold }
                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 580 ? (general.editor.draftLoader === "Vanilla" ? 2 : 3) : 1
                    columnSpacing: Style.value(general.appearance, "editorGeneralColumnSpacing2")
                    rowSpacing: Style.value(general.appearance, "editorGeneralRowSpacing2")
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: Style.value(general.appearance, "editorGeneralSpacing4")
                        UG.UiText { tag: "ui.editor.general.minecraft.label"; textKey: "builds.minecraft" }
                        UG.ComboBox {
                            id: minecraftChoice
                            tag: "ui.editor.general.minecraft"
                            objectName: "editor.minecraft"
                            Layout.fillWidth: true
                            density: "compact"
                            searchable: true
                            enabled: general.editable
                            valueRole: "key"; textRole: "text"; secondaryRole: "secondary"
                            model: {
                                Session.minecraftVersions
                                Session.coreChoicesRevision
                                Session.locale
                                const values = Session.versionOptions("Vanilla", "")
                                const options = values.some(option => option.value === general.editor.draftMinecraft) || !general.editor.draftMinecraft.length ? values : [{value: general.editor.draftMinecraft, label: general.editor.draftMinecraft}].concat(values)
                                return options.map(option => ({key: String(option.value || "__all__"), text: option.label, secondary: option.note || "", pinned: !!option.pinned, enabled: option.enabled !== false}))
                            }
                            selectedKey: general.editor.draftMinecraft || "__all__"
                            onSelectionRequested: selected => { general.editor.draftMinecraft = selected === "__all__" ? "" : selected; general.editor.markFormDirty() }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: Style.value(general.appearance, "editorGeneralSpacing4")
                        UG.UiText { tag: "ui.editor.general.loader.label"; textKey: "builds.loader" }
                        UG.ComboBox {
                            id: loaderChoice
                            tag: "ui.editor.general.loader"
                            objectName: "editor.loader"
                            Layout.fillWidth: true
                            density: "compact"
                            enabled: general.editable
                            valueRole: "key"; textRole: "text"
                            model: ["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"].map(value => ({key: value, text: value}))
                            selectedKey: general.editor.draftLoader
                            onSelectionRequested: selected => { general.editor.draftLoader = selected; general.editor.markFormDirty() }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: Style.value(general.appearance, "editorGeneralSpacing4")
                        visible: general.editor.draftLoader !== "Vanilla"
                        UG.UiText { tag: "ui.editor.general.loader_version.label"; textKey: "builds.loader_version" }
                        UG.ComboBox {
                            id: loaderVersionChoice
                            tag: "ui.editor.general.loader_version"
                            objectName: "editor.loaderVersion"
                            Layout.fillWidth: true
                            density: "compact"
                            searchable: true
                            valueRole: "key"; textRole: "text"; secondaryRole: "secondary"
                            textKey: general.editor.versionsBusy ? "versions.loading" : "versions.empty"
                            enabled: general.editable && !general.editor.versionsBusy && (general.editor.loaderVersions.length > 0 || general.editor.draftLoaderVersion.length > 0)
                            model: {
                                Session.locale
                                const options = Session.live ? general.editor.loaderOptions.map(option => ({key: option.value, text: option.label, secondary: option.installed ? Session.text("cores.installed") : ""})) : Session.versionOptions(general.editor.draftLoader, general.editor.draftMinecraft).map(option => ({key: option.value, text: option.label, secondary: option.note || ""}))
                                const current = general.editor.draftLoaderVersion
                                return current && !options.some(option => option.key === current) ? [{key: current, text: current}].concat(options) : options
                            }
                            selectedKey: general.editor.draftLoaderVersion || "__all__"
                            onSelectionRequested: selected => { general.editor.draftLoaderVersion = selected === "__all__" ? "" : selected; general.editor.markFormDirty() }
                        }
                    }
                }
            }
        }

        UG.Frame {
            tag: "ui.editor.general.window"
            Layout.fillWidth: true
            padding: Style.value(general.appearance, "editorGeneralPadding")
            contentItem: ColumnLayout {
                spacing: Style.value(general.appearance, "editorGeneralSpacing3")
                UG.UiText { tag: "ui.editor.general.window.heading"; textKey: "editor.window_size"; font.weight: Font.DemiBold }
                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 520 ? 2 : 1
                    columnSpacing: Style.value(general.appearance, "editorGeneralColumnSpacing"); rowSpacing: Style.value(general.appearance, "editorGeneralRowSpacing2")
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: Style.value(general.appearance, "editorGeneralSpacing2")
                        UG.TextField {
                            tag: "ui.editor.general.window.width"
                            displayText: String(Session.gameWindowDefaults.width)
                            useDisplayText: true
                            objectName: "editor.window.width"
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            placeholderText: String(Session.gameWindowDefaults.width)
                            text: general.editor.draftWidth
                            enabled: general.editable
                            validator: IntValidator { bottom: Session.gameWindowDefaults.minimumWidth; top: Session.gameWindowDefaults.maximumDimension }
                            Accessible.name: Session.text("editor.window_width")
                            onTextEdited: { general.editor.draftWidth = text; general.editor.markFormDirty() }
                        }
                        UG.UiText { tag: "ui.editor.general.window.separator"; displayText: "×" }
                        UG.TextField {
                            tag: "ui.editor.general.window.height"
                            displayText: String(Session.gameWindowDefaults.height)
                            useDisplayText: true
                            objectName: "editor.window.height"
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            placeholderText: String(Session.gameWindowDefaults.height)
                            text: general.editor.draftHeight
                            enabled: general.editable
                            validator: IntValidator { bottom: Session.gameWindowDefaults.minimumHeight; top: Session.gameWindowDefaults.maximumDimension }
                            Accessible.name: Session.text("editor.window_height")
                            onTextEdited: { general.editor.draftHeight = text; general.editor.markFormDirty() }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        UG.UiText { tag: "ui.editor.general.fullscreen.label"; Layout.fillWidth: true; textKey: "editor.fullscreen" }
                        UG.Switch {
                            tag: "ui.editor.general.fullscreen"
                            displayText: ""
                            useDisplayText: true
                            objectName: "editor.window.fullscreen"
                            implicitWidth: Style.value(general.appearance, "editorGeneralImplicitWidth3")
                            enabled: general.editable
                            checked: general.editor.draftFullscreen
                            onToggled: { general.editor.draftFullscreen = checked; general.editor.markFormDirty() }
                        }
                    }
                }
            }
        }

        UG.Frame {
            tag: "ui.editor.general.description"
            Layout.fillWidth: true
            padding: Style.value(general.appearance, "editorGeneralPadding")
            contentItem: ColumnLayout {
                spacing: Style.value(general.appearance, "editorGeneralSpacing3")
                RowLayout {
                    Layout.fillWidth: true
                    UG.UiText { tag: "ui.editor.general.description.heading"; Layout.fillWidth: true; textKey: "editor.description"; font.weight: Font.DemiBold }
                    UG.ComboBox {
                        id: formatChoice
                        tag: "ui.editor.general.description.format"
                        objectName: "editor.description.format"
                        implicitWidth: Style.value(general.appearance, "editorGeneralImplicitWidth4")
                        density: "compact"
                        enabled: general.editable
                        valueRole: "key"; textRole: "text"
                        model: { Session.revision; return ["md", "html"].map(key => ({key: key, text: Session.text("editor.format." + key)})) }
                        selectedKey: general.editor.draftDescriptionFormat
                        onSelectionRequested: selected => { general.editor.draftDescriptionFormat = selected; general.editor.markFormDirty() }
                    }
                }
                RowLayout {
                    spacing: Style.value(general.appearance, "editorGeneralSpacing2")
                    UG.Button {
                        tag: "ui.editor.general.description.edit"
                        objectName: "editor.description.edit"
                        textKey: "editor.description_edit"
                        implicitWidth: Style.value(general.appearance, "editorGeneralImplicitWidth5")
                        checked: !general.descriptionPreview
                        onClicked: general.descriptionPreview = false
                    }
                    UG.Button {
                        tag: "ui.editor.general.description.preview"
                        objectName: "editor.description.preview"
                        textKey: "editor.description_preview"
                        implicitWidth: Style.value(general.appearance, "editorGeneralImplicitWidth5")
                        checked: general.descriptionPreview
                        onClicked: general.descriptionPreview = true
                    }
                }
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(Style.value(general.appearance, "editorGeneralPreferredHeight"), general.appearance ? general.appearance.descriptionEditorHeight : Style.value(general.appearance, "editorGeneralPreferredHeight"))
                    UG.TextEditor {
                        id: sourceEditor
                        tag: "ui.editor.description.source"
                        objectName: "editor.description.source"
                        anchors.fill: parent
                        opacity: general.descriptionPreview ? 0 : 1
                        visible: opacity > 0
                        enabled: !general.descriptionPreview
                        wrap: Session.settings.editorWrap
                        lineNumbers: Session.settings.editorLineNumbers
                        readOnly: !general.editable
                        document: general.descriptionBuffer
                        Binding { target: sourceEditor.editor.Keys; property: "enabled"; value: false }
                        Behavior on opacity { NumberAnimation { duration: Session.settings.reducedMotion ? 0 : Style.value(general.appearance, "editorGeneralDuration") } }
                    }
                    UG.ScrollArea {
                        id: descriptionResult
                        tag: "ui.editor.general.description.result"
                        anchors.fill: parent
                        opacity: general.descriptionPreview ? 1 : 0
                        visible: opacity > 0
                        contentHeight: descriptionText.height + 24
                        Behavior on opacity { NumberAnimation { duration: Session.settings.reducedMotion ? 0 : Style.value(general.appearance, "editorGeneralDuration") } }
                        UG.UiText {
                            id: descriptionText
                            tag: "ui.editor.general.description.rendered"
                            objectName: "editor.description.rendered"
                            x: 12; y: 12
                            width: Math.max(0, descriptionResult.width - Style.value(general.appearance, "editorGeneralWidth3"))
                            useDisplayText: true
                            displayText: general.descriptionPreview ? general.editor.draftDescription.trim() ? Session.renderDescription(general.editor.draftDescription, general.editor.draftDescriptionFormat) : Session.text("editor.description_empty") : ""
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }
    }
    Connections {
        target: minecraftChoice
        function onSelectedKeyChanged() { Qt.callLater(general.syncSelections) }
    }
    Connections {
        target: loaderChoice
        function onSelectedKeyChanged() { Qt.callLater(general.syncSelections) }
    }
    Connections {
        target: loaderVersionChoice
        function onSelectedKeyChanged() { Qt.callLater(general.syncSelections) }
    }
    Connections {
        target: formatChoice
        function onSelectedKeyChanged() { Qt.callLater(general.syncSelections) }
    }
}
