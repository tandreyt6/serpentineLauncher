import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG

Item {
    id: page
    property bool changes: false
    ColumnLayout {
        anchors.fill: parent
        spacing: Style.value((page.Window.window ? page.Window.window.appearance : null), "aboutSettingsSpacing")
        RowLayout {
            UG.Button {
                tag: "ui.about.program"
                textKey: "about.program"
                stateKey: page.changes ? "secondary" : "primary"
                onActivated: page.changes = false
            }
            UG.Button {
                tag: "ui.about.changes"
                textKey: "about.new"
                stateKey: page.changes ? "primary" : "secondary"
                onActivated: page.changes = true
            }
        }
        UG.DocumentView {
            tag: "ui.about.document"
            Layout.fillWidth: true
            Layout.fillHeight: true
            format: "markdown"
            source: {
                Session.revision
                return Session.text(page.changes ? "about.changes" : "about.body")
            }
            onLinkRequested: link => {
                if (/^https?:\/\//i.test(link))
                    Session.command("external_link", link)
            }
        }
    }
}
