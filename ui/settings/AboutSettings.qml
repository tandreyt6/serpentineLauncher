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
        RowLayout {
            Layout.fillWidth: true
            UG.Button {
                tag: "ui.updates.check"
                objectName: "updates.check"
                textKey: "updates.check"
                enabled: !Updates.busy
                onActivated: Updates.check()
            }
            Item { Layout.fillWidth: true }
            UG.Switch {
                tag: "ui.updates.silent"
                objectName: "updates.silent"
                textKey: "updates.silent"
                checkable: false
                checked: Session.settings.silentUpdates
                onClicked: Session.command("setting", "silentUpdates", (!Session.settings.silentUpdates).toString())
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
