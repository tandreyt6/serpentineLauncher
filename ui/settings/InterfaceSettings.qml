import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher

UG.ScrollArea {
    id: scroll
    tag: "settings.scroll.interfacesettings"
    ColumnLayout {
        width: Math.max(0, scroll.width - scroll.appearance.scrollbarWidth - Style.value(scroll.appearance, "interfaceSettingsWidth"))
        spacing: Style.value(scroll.appearance, "interfaceSettingsSpacing")
        UG.Frame {
            tag: "settings.card.rendering"
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "interfaceSettingsSpacing")
                UG.FormRow {
                    tag: "settings.row.hardwareAcceleration"
                    textKey: "settings.hardware_acceleration"
                    Layout.fillWidth: true
                    UG.SwitchBox {
                        tag: "settings.control.hardwareAcceleration"
                        textKey: "settings.hardware_acceleration"
                        checked: Boolean(Session.settings.hardwareAcceleration)
                        onClicked: Session.command("setting", "hardwareAcceleration", (!Session.settings.hardwareAcceleration).toString())
                    }
                }
                UG.UiText {
                    tag: "settings.rendering.restart"
                    textKey: "settings.rendering_restart"
                    visible: Boolean(Session.settings.hardwareAcceleration) !== Gui.hardwareAcceleration
                    Layout.fillWidth: true
                }
            }
        }
        UG.Frame {
            tag: "settings.card.collections"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "interfaceSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.collections"
                    textKey: "settings.collections"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.buildView"
                    textKey: "settings.build_view"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: buildViewChoice
                        density: "compact"
                        tag: "settings.control.buildView"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "cards",
                                    text: Session.text("common.cards")
                                },
                                {
                                    key: "list",
                                    text: Session.text("common.list")
                                }
                            ]
                        }
                        selectedKey: Session.settings.buildView
                        onSelectionRequested: key => Session.command("setting", "buildView", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.buildCardSize"
                    textKey: "settings.card_size"
                    Layout.fillWidth: true
                    StepSlider {
                        id: buildCardSizeChoice
                        tag: "settings.control.buildCardSize"
                        Layout.fillWidth: true
                        stepCount: Session.cardSizeOptions.length
                        reducedMotion: Boolean(Session.settings.reducedMotion)
                        to: stepCount - 1
                        enabled: Session.settings.buildView === "cards"
                        value: enabled ? Math.max(0, Session.cardSizeOptions.findIndex(option => option.key === Session.settings.buildCardSize)) : 3
                        tooltipDelay: Number(Session.settings.tooltipDelayMs)
                        tooltip: Session.text(Session.cardSizeOptions[Math.round(previewValue)].text_key)
                        Accessible.name: Session.text("settings.card_size")
                        onValueCommitted: chosen => {
                            const option = Session.cardSizeOptions[Math.round(chosen)]
                            if (enabled && option.key !== Session.settings.buildCardSize)
                                Session.command("setting", "buildCardSize", option.key)
                        }
                    }
                }
                UG.FormRow {
                    tag: "settings.row.buildDoubleClickAction"
                    textKey: "settings.build_double_click"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        tag: "settings.control.buildDoubleClickAction"
                        objectName: "settings.buildDoubleClickAction"
                        density: "compact"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return Session.buildDoubleClickOptions.map(option => ({
                                        key: option.key,
                                        text: Session.text(option.text_key)
                                    }))
                        }
                        selectedKey: Session.settings.buildDoubleClickAction
                        onSelectionRequested: key => Session.command("setting", "buildDoubleClickAction", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.coreView"
                    textKey: "settings.core_view"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: coreViewChoice
                        density: "compact"
                        tag: "settings.control.coreView"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "cards",
                                    text: Session.text("common.cards")
                                },
                                {
                                    key: "list",
                                    text: Session.text("common.list")
                                }
                            ]
                        }
                        selectedKey: Session.settings.coreView
                        onSelectionRequested: key => Session.command("setting", "coreView", key)
                    }
                }
            }
        }
        UG.Frame {
            tag: "settings.card.notifications"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "interfaceSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.notifications"
                    textKey: "settings.notifications"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.tooltipDelayMs"
                    textKey: "settings.tooltip_delay"
                    Layout.fillWidth: true
                    NumberSettingField {
                        tag: "settings.control.tooltipDelayMs"
                        objectName: "settings.tooltipDelayMs"
                        settingKey: "tooltipDelayMs"
                        displayText: ""
                        useDisplayText: true
                        Layout.preferredWidth: Style.value(scroll.appearance, "interfaceSettingsPreferredWidth")
                        Layout.alignment: Qt.AlignRight
                        suffixText: Session.text("common.ms")
                    }
                }
                UG.FormRow {
                    tag: "settings.row.notificationDurationMs"
                    textKey: "settings.notification_duration"
                    Layout.fillWidth: true
                    NumberSettingField {
                        tag: "settings.control.notificationDurationMs"
                        settingKey: "notificationDurationMs"
                        displayText: ""
                        useDisplayText: true
                        Layout.preferredWidth: Style.value(scroll.appearance, "interfaceSettingsPreferredWidth")
                        Layout.alignment: Qt.AlignRight
                        suffixText: Session.text("common.ms")
                    }
                }
                UG.FormRow {
                    tag: "settings.row.notificationPolicy"
                    textKey: "settings.notification_policy"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: notificationPolicyChoice
                        density: "compact"
                        tag: "settings.control.notificationPolicy"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "drop-oldest",
                                    text: Session.text("settings.drop_oldest")
                                },
                                {
                                    key: "replace-current",
                                    text: Session.text("settings.replace_current")
                                },
                                {
                                    key: "reject-new",
                                    text: Session.text("settings.reject_new")
                                }
                            ]
                        }
                        selectedKey: Session.settings.notificationPolicy
                        onSelectionRequested: key => Session.command("setting", "notificationPolicy", key)
                    }
                }
            }
        }
        UG.Frame {
            tag: "settings.card.tasks"
            displayText: ""
            useDisplayText: true
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Style.value(scroll.appearance, "interfaceSettingsSpacing")
                UG.UiText {
                    tag: "settings.title.tasks"
                    textKey: "activity.open"
                    typographyRole: "heading"
                    Layout.fillWidth: true
                }
                UG.FormRow {
                    tag: "settings.row.tasksDisplay"
                    textKey: "settings.task_display"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        id: tasksDisplayChoice
                        density: "compact"
                        tag: "settings.control.tasksDisplay"
                        textKey: "common.choose"
                        valueRole: "key"
                        textRole: "text"
                        Layout.fillWidth: true
                        model: {
                            Session.revision
                            return [
                                {
                                    key: "active",
                                    text: Session.text("settings.active_task")
                                },
                                {
                                    key: "latest",
                                    text: Session.text("settings.latest_task")
                                }
                            ]
                        }
                        selectedKey: Session.settings.tasksDisplay
                        onSelectionRequested: key => Session.command("setting", "tasksDisplay", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.downloadRetries"
                    textKey: "settings.download_retries"
                    Layout.fillWidth: true
                    UG.ComboBox {
                        tag: "settings.control.downloadRetries"
                        objectName: "settings.downloadRetries"
                        density: "compact"
                        Layout.fillWidth: true
                        valueRole: "key"
                        textRole: "text"
                        model: [0, 1, 2, 3, 4, 5].map(value => ({
                                    key: String(value),
                                    text: String(value)
                                }))
                        selectedKey: Session.settings.downloadRetries
                        onSelectionRequested: key => Session.command("setting", "downloadRetries", key)
                    }
                }
                UG.FormRow {
                    tag: "settings.row.tasksAutoOpen"
                    textKey: "settings.tasks_auto_open"
                    Layout.fillWidth: true
                    UG.Switch {
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: Style.value(scroll.appearance, "interfaceSettingsTopMargin")
                        Layout.bottomMargin: Style.value(scroll.appearance, "interfaceSettingsBottomMargin")
                        Layout.rightMargin: Style.value(scroll.appearance, "interfaceSettingsRightMargin")
                        tag: "settings.control.tasksAutoOpen"
                        displayText: ""
                        useDisplayText: true

                        checkable: false
                        checked: Session.settings.tasksAutoOpen
                        onClicked: Session.command("setting", "tasksAutoOpen", (!Session.settings.tasksAutoOpen).toString())
                    }
                }
            }
        }
    }
}
