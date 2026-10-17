import QtQuick
import QtQuick.Controls as QC
import Working.Gui as UG

UG.ConfirmationDialog {
    parent: QC.Overlay.overlay
    tag: "ui.first_run"
    objectName: "firstRun.reminder"
    heading: Session.text("first_run.heading")
    message: Session.text("first_run.profile") + (Session.firstRunJavaFound ? "" : "\n\n" + Session.text("first_run.java_missing"))
    actions: [
        {key: "close", text_key: "common.close"},
        {key: "profile", text_key: "first_run.open_profile", state_key: "primary"}
    ]
    cancelAction: "close"
    defaultAction: "profile"
    onActionRequested: key => {
        Session.acknowledgeFirstRun()
        if (key === "profile")
            Session.command("navigate", "profile")
    }
    onCancelled: Session.acknowledgeFirstRun()
}
