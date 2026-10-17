import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QC
import Working.Gui as UG
import Launcher

UG.Page {
    id: page
    property string deleting: ""
    property string editing: ""
    property string draftName: ""
    tag: "ui.page"
    objectName: "page.profile"
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: page.appearance.pageMargin
        spacing: Style.value(page.appearance, "profilePageSpacing")
        RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value(page.appearance, "profilePageImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.profilepage.1"
                stateKey: (true) ? "primary" : "secondary"
                textKey: "profile.add"
                iconSource: IconSources["add"] || ""
                onClicked: {
                    page.editing = ""
                    page.draftName = ""
                    addAccount.open()
                }
            }
        }
        UG.ScrollArea {
            id: scroll
            tag: "ui.scroll.profilepage.0"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: width

            Column {
                width: scroll.width
                spacing: Style.value(page.appearance, "profilePageSpacing2")
                Repeater {
                    model: Session.accounts
                    delegate: UG.Frame {
                        tag: "ui.pages.profilepage.2"
                        padding: 0
                        displayText: ""
                        useDisplayText: true
                        stateKey: (Session.activeAccountId === modelData.id) ? "selected" : ""

                        required property var modelData
                        width: parent.width
                        height: page.appearance.profileRowHeight
                        objectName: "profile.row." + modelData.id

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Style.value(page.appearance, "profilePageMargins")
                            spacing: Style.value(page.appearance, "profilePageSpacing3")
                            Rectangle {
                                Layout.preferredWidth: Style.value(page.appearance, "profilePagePreferredWidth")
                                Layout.preferredHeight: Style.value(page.appearance, "profilePagePreferredHeight")
                                radius: Style.value(page.appearance, "profilePageRadius")
                                color: page.appearance.selection
                                Image {
                                    anchors.fill: parent
                                    source: ImageFiles["account-default"] || ""
                                    fillMode: Image.PreserveAspectFit
                                    visible: source.toString().length > 0
                                }
                                UG.Icon {
                                    tag: "ui.pages.profilepage.3"
                                    anchors.centerIn: parent
                                    width: Style.value(page.appearance, "profilePageWidth")
                                    height: Style.value(page.appearance, "profilePageHeight")
                                    source: IconSources["profile"] || ""
                                    tint: page.appearance.accent
                                    visible: !ImageFiles["account-default"]
                                }
                            }
                            UG.UiText {
                                tag: "ui.pages.profilepage.4"
                                verticalAlignment: Text.AlignVCenter
                                Layout.fillWidth: true
                                displayText: modelData.name
                                font.pixelSize: Style.value(page.appearance, "profilePagePixelSize")
                                font.weight: Font.DemiBold
                                wrapMode: Text.NoWrap
                                elide: Text.ElideRight
                            }
                            UG.UiText {
                                tag: "ui.pages.profilepage.5"
                                verticalAlignment: Text.AlignVCenter
                                textKey: "common.offline"
                                typographyRole: (true) ? "caption" : "body"
                                Layout.preferredWidth: Style.value(page.appearance, "profilePagePreferredWidth2")
                                wrapMode: Text.NoWrap
                            }
                            UG.Button {
                                id: button1
                                implicitWidth: Math.max(Style.value(page.appearance, "profilePageImplicitWidth"), metrics1.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                TextMetrics {
                                    id: metrics1
                                    text: button1.text
                                    font.family: button1.appearance.fontFamily
                                    font.pixelSize: button1.appearance.fontSize
                                    font.weight: Font.DemiBold
                                }

                                tag: "ui.pages.profilepage.6"
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
                                    }[Session.activeAccount === modelData.name ? "common.selected" : "profile.select"] || ""] || ""
                                objectName: "profile.select." + modelData.id
                                Layout.preferredWidth: page.appearance.profileActionWidth
                                textKey: Session.activeAccount === modelData.name ? "common.selected" : "profile.select"
                                enabled: Session.activeAccount !== modelData.name
                                onClicked: Session.command("account", modelData.id)
                            }
                            UG.Button {
                                id: button2
                                implicitWidth: Math.max(Style.value(page.appearance, "profilePageImplicitWidth"), metrics2.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                TextMetrics {
                                    id: metrics2
                                    text: button2.text
                                    font.family: button2.appearance.fontFamily
                                    font.pixelSize: button2.appearance.fontSize
                                    font.weight: Font.DemiBold
                                }

                                tag: "ui.pages.profilepage.7"
                                stateKey: (false) ? "primary" : "secondary"
                                displayText: ""
                                useDisplayText: true
                                objectName: "profile.edit." + modelData.id
                                iconSource: IconSources["edit"] || ""
                                width: Style.value(page.appearance, "profilePageWidth2")
                                Accessible.name: Session.text("profile.edit")
                                QC.ToolTip.visible: hovered
                                QC.ToolTip.text: Accessible.name
                                onClicked: {
                                    page.editing = modelData.id
                                    page.draftName = modelData.name
                                    addAccount.open()
                                }
                            }
                            UG.Button {
                                id: button3
                                implicitWidth: Math.max(Style.value(page.appearance, "profilePageImplicitWidth"), metrics3.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                                TextMetrics {
                                    id: metrics3
                                    text: button3.text
                                    font.family: button3.appearance.fontFamily
                                    font.pixelSize: button3.appearance.fontSize
                                    font.weight: Font.DemiBold
                                }

                                tag: "ui.pages.profilepage.8"
                                stateKey: (false) ? "primary" : "secondary"
                                displayText: ""
                                useDisplayText: true
                                iconSource: IconSources["delete"] || ""
                                width: Style.value(page.appearance, "profilePageWidth2")
                                onClicked: {
                                    page.deleting = modelData.id
                                    deleteAccount.detail = modelData.name
                                    deleteAccount.open()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    UG.PopupPanel {
        id: addAccount
        height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, parent ? parent.height : Style.value(page.appearance, "profilePageHeight2"))

        tag: "ui.pages.profilepage.9"
        anchors.centerIn: QC.Overlay.overlay
        width: Style.value(page.appearance, "profilePageWidth3")
        padding: page.appearance.dialogPadding
        modal: true
        focus: true
        objectName: "profile.accountDialog"
        onAboutToShow: {
            accountName.text = page.draftName
            accountName.forceActiveFocus()
            accountName.selectAll()
        }
        background: UG.Frame {
            tag: "ui.pages.profilepage.10"
            padding: 0
            displayText: ""
            useDisplayText: true
        }
        contentItem: ColumnLayout {
            UG.UiText {
                tag: "ui.pages.profilepage.11"
                verticalAlignment: Text.AlignVCenter
                textKey: page.editing.length ? "profile.edit" : "profile.add"
                font.weight: Font.DemiBold
            }
            UG.TextField {
                id: accountName
                tag: "ui.pages.profilepage.12"
                objectName: "profile.accountName"
                Layout.fillWidth: true
                textKey: "profile.name"
                maximumLength: 16
                validator: RegularExpressionValidator {
                    regularExpression: /[A-Za-z0-9_]{0,16}/
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                UG.Button {
                    id: button4
                    implicitWidth: Math.max(Style.value(page.appearance, "profilePageImplicitWidth"), metrics4.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                    TextMetrics {
                        id: metrics4
                        text: button4.text
                        font.family: button4.appearance.fontFamily
                        font.pixelSize: button4.appearance.fontSize
                        font.weight: Font.DemiBold
                    }

                    tag: "ui.pages.profilepage.13"
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
                        }["common.cancel"] || ""] || ""
                    textKey: "common.cancel"
                    onClicked: addAccount.close()
                }
                UG.Button {
                    id: button5
                    implicitWidth: Math.max(Style.value(page.appearance, "profilePageImplicitWidth"), metrics5.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                    TextMetrics {
                        id: metrics5
                        text: button5.text
                        font.family: button5.appearance.fontFamily
                        font.pixelSize: button5.appearance.fontSize
                        font.weight: Font.DemiBold
                    }

                    tag: "ui.pages.profilepage.14"
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
                        }[page.editing.length ? "common.save" : "common.add"] || ""] || ""
                    objectName: "profile.accountConfirm"
                    textKey: page.editing.length ? "common.save" : "common.add"
                    enabled: accountName.text.length >= 3
                    onClicked: {
                        Session.command(page.editing.length ? "rename_account" : "add_account", page.editing, accountName.text)
                        addAccount.close()
                    }
                }
            }
        }
    }
    UG.ConfirmationDialog {
        id: deleteAccount
        tag: "ui.pages.profilepage.15"
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
        heading: Session.text("profile.delete_title")
        message: Session.text("profile.delete_hint")
        onActionRequested: action => {
            if (action === "accept")
                Session.command("delete_account", page.deleting)
        }
    }
}
