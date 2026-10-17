import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher

UG.Page {
    id: page
    tag: "ui.page"
    objectName: "page.buildAbout"
    readonly property var buildData: {
        Session.builds
        return Session.build(Session.aboutBuildId)
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: page.appearance.pageMargin
        spacing: Style.value(page.appearance, "buildAboutPageSpacing")
        RowLayout {
            Layout.fillWidth: true
            UG.Button {
                id: button0
                implicitWidth: Math.max(Style.value(page.appearance, "buildAboutPageImplicitWidth"), metrics0.advanceWidth + 2 * appearance.controlPadding + (String(iconSource).length ? appearance.iconSize + appearance.iconGap : 0))
                TextMetrics {
                    id: metrics0
                    text: button0.text
                    font.family: button0.appearance.fontFamily
                    font.pixelSize: button0.appearance.fontSize
                    font.weight: Font.DemiBold
                }

                tag: "ui.pages.buildaboutpage.1"
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
                    }["common.back"] || ""] || ""
                textKey: "common.back"
                objectName: "buildAbout.back"
                onClicked: Session.command("back", "")
            }
            UG.UiText {
                tag: "ui.pages.buildaboutpage.2"
                verticalAlignment: Text.AlignVCenter
                Layout.fillWidth: true
                displayText: page.buildData.title || ""
                wrapMode: Text.NoWrap
                font.pixelSize: Style.value(page.appearance, "buildAboutPagePixelSize")
                font.weight: Font.DemiBold
            }
            UG.UiText {
                tag: "ui.pages.buildaboutpage.3"
                verticalAlignment: Text.AlignVCenter
                displayText: (page.buildData.minecraft || "") + " · " + (page.buildData.loader || "")
                typographyRole: (true) ? "caption" : "body"
            }
        }
        UG.DocumentView {
            tag: "ui.pages.buildaboutpage.4"
            onLinkRequested: url => {
                if (/^https?:/.test(url))
                    Qt.openUrlExternally(url)
            }

            objectName: "buildAbout.description"
            Layout.fillWidth: true
            Layout.fillHeight: true
            source: {
                Session.revision
                return page.buildData.description_key ? Session.text(page.buildData.description_key) : ""
            }
            format: (page.buildData.description_format || "md") === "md" ? "markdown" : "html"
        }
    }
}
