import "../Launcher/Style.js" as Style
import QtQuick
import Working.Gui as UG
import QtQuick.Layouts
import QtQuick.Controls as QC
import QtQuick.Dialogs
import Launcher

UG.ScrollArea {
    id: scroll
    tag: "ui.scroll.javasettings.0"
    clip: true
    contentWidth: width

    FileDialog {
        id: javaPicker
        objectName: "settings.java.picker"
        title: {
            Session.revision
            return Session.text("settings.java_path")
        }
        fileMode: FileDialog.OpenFile
        nameFilters: {
            Session.revision
            return Qt.platform.os === "windows" ? [Session.text("settings.java_files"), Session.text("common.all_files")] : [Session.text("common.all_files")]
        }
        onAccepted: Session.chooseJavaFile(selectedFile.toString())
    }
    ColumnLayout {
        width: scroll.width
        spacing: layoutStyle.appearance.layoutGap
        UG.Frame {
            id: layoutStyle

            tag: "ui.settings.javasettings.1"
            padding: 0
            displayText: ""
            useDisplayText: true

            Layout.fillWidth: true
            implicitHeight: content.implicitHeight + 2 * layoutStyle.appearance.cardPadding
            ColumnLayout {
                id: content
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: layoutStyle.appearance.cardPadding
                spacing: layoutStyle.appearance.layoutGap
                UG.UiText {
                    tag: "ui.settings.javasettings.2"
                    verticalAlignment: Text.AlignVCenter
                    textKey: "settings.java_path"
                    font.weight: Font.DemiBold
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: layoutStyle.appearance.smallGap
                    UG.TextField {
                        tag: "ui.settings.javasettings.3"
                        displayText: ""
                        useDisplayText: true
                        objectName: "settings.java.path"
                        Layout.fillWidth: true
                        text: Session.settings.javaPath
                    placeholderText: Session.text("editor.java_command_hint")
                        onEditingFinished: {
                            Session.command("setting", "javaPath", text)
                            text = Qt.binding(function () {
                                return Session.settings.javaPath
                            })
                        }
                    }
                    UG.Button {
                        id: button0
                        implicitWidth: Math.max(Style.value(scroll.appearance, "javaSettingsImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                        TextMetrics {
                            id: metrics0
                            text: button0.text
                            font.family: button0.appearance.fontFamily
                            font.pixelSize: button0.appearance.fontSize
                            font.weight: Font.DemiBold
                        }

                        tag: "ui.settings.javasettings.4"
                        stateKey: (false) ? "primary" : "secondary"
                        objectName: "settings.java.browse"
                        textKey: "common.browse"
                        iconSource: IconSources["folder-open"] || ""
                        onClicked: javaPicker.open()
                    }
                }
                UG.Button {
                    id: button1
                    implicitWidth: Math.max(Style.value(scroll.appearance, "javaSettingsImplicitWidth"), metrics1.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                    TextMetrics {
                        id: metrics1
                        text: button1.text
                        font.family: button1.appearance.fontFamily
                        font.pixelSize: button1.appearance.fontSize
                        font.weight: Font.DemiBold
                    }

                    tag: "ui.settings.javasettings.5"
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
                        }["settings.java_auto"] || ""] || ""
                    textKey: "settings.java_auto"
                    onClicked: Session.command("detect_java", "")
                }
                UG.FormRow {
                    tag: "ui.settings.javasettings.6"
                    Layout.fillWidth: true
                    textKey: "settings.java_version"
                    UG.ComboBox {
                        id: selection0
                        density: "compact"
                        tag: "ui.settings.javasettings.7"
                        valueRole: "key"
                        textRole: "text"
                        secondaryRole: "secondary"
                        Layout.preferredWidth: Style.value(scroll.appearance, "javaSettingsPreferredWidth")
                        model: {
                            const options = (function () {
                                    return [
                                        {
                                            value: "auto",
                                            label: "Auto"
                                        },
                                        {
                                            value: "25",
                                            label: "Java 25"
                                        },
                                        {
                                            value: "21",
                                            label: "Java 21"
                                        },
                                        {
                                            value: "17",
                                            label: "Java 17"
                                        },
                                        {
                                            value: "8",
                                            label: "Java 8"
                                        }
                                    ]
                                })()
                            return options.map(option => ({
                                        key: String(option.value === undefined ? option.key : option.value) || "__all__",
                                        text: option.label === undefined ? option.text : option.label,
                                        secondary: option.note || option.secondary || "",
                                        pinned: !!option.pinned,
                                        enabled: option.enabled !== false
                                    }))
                        }
                        selectedKey: (Session.settings.javaVersion) || "__all__"
                        onSelectionRequested: selected => {
                            const value = selected === "__all__" ? "" : selected
                            Session.command("setting", "javaVersion", value)
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: layoutStyle.appearance.border
                }
                UG.UiText {
                    tag: "ui.settings.javasettings.8"
                    verticalAlignment: Text.AlignVCenter
                    textKey: "settings.memory"
                    font.pixelSize: layoutStyle.appearance.sectionSize
                    font.weight: Font.DemiBold
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.value(scroll.appearance, "javaSettingsSpacing")
                    ColumnLayout {
                        Layout.fillWidth: true
                        UG.UiText {
                            tag: "ui.settings.javasettings.9"
                            verticalAlignment: Text.AlignVCenter
                            textKey: "settings.memory_min"
                            typographyRole: "body"
                        }
                        UG.TextField {
                            tag: "ui.settings.javasettings.10"
                            displayText: ""
                            useDisplayText: true
                            objectName: "settings.java.memoryMin"
                            Layout.fillWidth: true
                            text: Session.settings.memoryMin
                            validator: IntValidator {
                                bottom: 0
                                top: 999999
                            }
                            onEditingFinished: {
                                Session.command("setting", "memoryMin", text)
                                text = Qt.binding(function () {
                                    return Session.settings.memoryMin
                                })
                            }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        UG.UiText {
                            tag: "ui.settings.javasettings.11"
                            verticalAlignment: Text.AlignVCenter
                            textKey: "settings.memory_max"
                            typographyRole: "body"
                        }
                        UG.TextField {
                            tag: "ui.settings.javasettings.12"
                            displayText: ""
                            useDisplayText: true
                            objectName: "settings.java.memoryMax"
                            Layout.fillWidth: true
                            text: Session.settings.memoryMax
                            validator: IntValidator {
                                bottom: 0
                                top: 999999
                            }
                            onEditingFinished: {
                                Session.command("setting", "memoryMax", text)
                                text = Qt.binding(function () {
                                    return Session.settings.memoryMax
                                })
                            }
                        }
                    }
                }
                UG.UiText {
                    tag: "ui.settings.javasettings.13"
                    verticalAlignment: Text.AlignVCenter
                    textKey: "settings.jvm_args"
                    font.weight: Font.DemiBold
                }
                UG.TextField {
                    tag: "ui.settings.javasettings.14"
                    displayText: ""
                    useDisplayText: true
                    Layout.fillWidth: true
                    text: Session.settings.jvmArgs
                    placeholderText: "-XX:+UseG1GC"
                    onEditingFinished: Session.command("setting", "jvmArgs", text)
                }
            }
        }
    }
}
