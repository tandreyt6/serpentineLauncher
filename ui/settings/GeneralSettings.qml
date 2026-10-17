import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

UG.ScrollArea {
    id: scroll
    tag: "settings.scroll.general"
    ColumnLayout {
        width: Math.max(0, scroll.width - scroll.appearance.scrollbarWidth - Style.value(scroll.appearance, "generalSettingsWidth"))
        spacing: Style.value(scroll.appearance, "generalSettingsSpacing")
        UG.Frame {
            tag: "settings.card.appearance"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "generalSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.appearance"
                    textKey: "settings.appearance"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.language"
                    textKey: "settings.language"
                    Layout.fillWidth: true
                    RowLayout {
                        Layout.fillWidth: true
                        UG.ComboBox {
                            id: languageChoice
                            density: "compact"
                            tag: "settings.language.choice"
                            objectName: "settings.language.choice"
                            textKey: "common.choose"
                            Layout.fillWidth: true
                            searchable: true
                            valueRole: "key"
                            textRole: "text"
                            model: Session.languages.map(key => ({
                                        key: key,
                                        text: key === "ru" ? "Русский" : key === "en" ? "English" : key
                                    }))
                            selectedKey: Session.locale
                            onSelectionRequested: key => Session.command("locale", key)
                        }
                        UG.Button {
                            tag: "settings.language.refresh"
                            objectName: "settings.language.refresh"
                            textKey: "common.refresh"
                            stateKey: "secondary"
                            enabled: !Session.refreshingLanguages
                            onActivated: Session.refreshAppearance("languages")
                        }
                    }
                }
                UG.FormRow {
                    tag: "settings.row.theme"
                    textKey: "settings.theme"
                    Layout.fillWidth: true
                    RowLayout {
                        Layout.fillWidth: true
                        UG.ComboBox {
                            id: themeChoice
                            density: "compact"
                            tag: "settings.theme.choice"
                            objectName: "settings.theme.choice"
                            textKey: "common.choose"
                            Layout.fillWidth: true
                            searchable: true
                            valueRole: "key"
                            textRole: "text"
                            model: {
                                Session.revision
                                const failures = ThemeUI.failedThemes
                                return Session.themes.filter(key => key !== "office" && key !== "slate").map(key => ({
                                            key: key,
                                            text: key === "serpantine-night" || key === "serpantine-day" ? Session.text("theme." + key) : key,
                                            warning: failures[key] || ""
                                        }))
                            }
                            selectedKey: Session.theme
                            onSelectionRequested: key => ThemeUI.requestTheme(key)
                        }
                        UG.Button {
                            tag: "settings.theme.refresh"
                            objectName: "settings.theme.refresh"
                            textKey: "common.refresh"
                            stateKey: "secondary"
                            enabled: !Session.refreshingThemes
                            onActivated: Session.refreshAppearance("themes")
                        }
                    }
                }
                UG.FormRow {
                    tag: "settings.row.motion"
                    textKey: "settings.motion"
                    Layout.fillWidth: true
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "generalSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "generalSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "generalSettingsRightMargin")
                        tag: "settings.control.motion"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.reducedMotion
                        onClicked: Session.command("setting", "reducedMotion", (!Session.settings.reducedMotion).toString())
                    }
                }
            }
        }
    }
}
