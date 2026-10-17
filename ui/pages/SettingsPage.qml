import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import "../settings" as Settings

UG.Page {
    id: page
    tag: "ui.settings"
    objectName: "page.settings"
    Component.onCompleted: ThemeUI.restorePageState(page, "page.settings")
    property string section: "general"
    signal navigationSettingsRequested()
    RowLayout {
        anchors.fill: parent
        anchors.margins: page.appearance.pageMargin
        spacing: Style.value(page.appearance, "settingsPageSpacing")
        ColumnLayout {
            Layout.preferredWidth: page.appearance.settingsMenuWidth
            Layout.minimumWidth: page.appearance.settingsMenuWidth
            Layout.maximumWidth: page.appearance.settingsMenuWidth
            Layout.fillHeight: true
            spacing: Style.value(page.appearance, "settingsPageSpacing2")
            UG.Button {
                tag: "settings.back"
                textKey: "common.back"
                stateKey: "secondary"
                iconSource: IconSources["back"] || ""
                onActivated: Session.command("back", "")
            }
            UG.UiText {
                tag: "settings.heading"
                textKey: "settings.heading"
                typographyRole: "heading"
                Layout.topMargin: Style.value(page.appearance, "settingsPageTopMargin")
                Layout.bottomMargin: Style.value(page.appearance, "settingsPageBottomMargin")
            }
            Repeater {
                model: ["general", "interface", "java", "panel", "shortcuts", "behavior", "editor", "logging", "about"]
                UG.Button {
                    required property string modelData
                    tag: "settings.navigation"
                    textKey: "settings." + modelData
                    stateKey: page.section === modelData ? "primary" : "secondary"
                    textAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    objectName: "settings." + modelData
                    onActivated: page.section = modelData
                }
            }
            Item {
                Layout.fillHeight: true
            }
        }
        Rectangle {
            width: 1
            color: page.appearance.border
            Layout.fillHeight: true
        }
        UG.AnimatedStack {
            id: stack
            tag: "settings.sections"
            objectName: "settings.sections"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: Style.value(page.appearance, "settingsPageMinimumWidth")
            retentionPolicy: "bounded"
            maximumRetained: 3
            currentKey: page.section
            pages: [
                {
                    key: "general",
                    component: generalPage
                },
                {
                    key: "interface",
                    component: interfacePage
                },
                {
                    key: "java",
                    component: javaPage
                },
                {
                    key: "panel",
                    component: panelPage
                },
                {
                    key: "shortcuts",
                    component: shortcutsPage
                },
                {
                    key: "behavior",
                    component: behaviorPage
                },
                {
                    key: "editor",
                    component: editorPage
                },
                {
                    key: "logging",
                    component: loggingPage
                },
                {
                    key: "about",
                    component: aboutPage
                }
            ]
            Component {
                id: generalPage
                Settings.GeneralSettings {}
            }
            Component {
                id: interfacePage
                Settings.InterfaceSettings {}
            }
            Component {
                id: javaPage
                Settings.JavaSettings {}
            }
            Component {
                id: panelPage
                Settings.PanelSettings {
                    onLivePreviewRequested: page.navigationSettingsRequested()
                }
            }
            Component {
                id: shortcutsPage
                Settings.ShortcutSettings {}
            }
            Component {
                id: behaviorPage
                Settings.BehaviorSettings {}
            }
            Component {
                id: editorPage
                Settings.EditorSettings {}
            }
            Component {
                id: loggingPage
                Settings.LoggingSettings {}
            }
            Component {
                id: aboutPage
                Settings.AboutSettings {}
            }
        }
    }
}
