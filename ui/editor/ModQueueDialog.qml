import "../Launcher/Style.js" as Style
import QtQuick
import Working.Gui as UG

UG.ConfirmationDialog {
    id: dialog
    required property string buildId
    required property string workspaceKey
    property var question: ({})
    property string requestId: ""
    readonly property bool duplicateQuestion: question.kind !== "dependencies"
    objectName: "mod.queue.question." + buildId
    tag: "editor.mod_queue.question"
    width: Math.min(Style.value(dialog.appearance, "modQueueDialogWidth"), Math.max(0, ownerWidth - Style.value(dialog.appearance, "modQueueDialogWidth2")))
    heading: Session.text(duplicateQuestion ? "editor.mod_duplicate" : (question.conflicts || []).some(item => item.disabled) ? "editor.mod_dependencies_attention" : "editor.mod_dependencies_conflict")
    message: (question.title || "") + "\n" + Session.text(question.kind === "file" ? "editor.mod_same_file_question" : question.kind === "same" ? "editor.mod_same_version_question" : duplicateQuestion ? "editor.mod_duplicate_question" : "editor.mod_dependencies_question")
    detail: duplicateQuestion ? [
        question.filename ? Session.text("editor.mod_filename") + ": " + question.filename : "",
        question.version ? Session.text("editor.mod_new_version") + ": " + question.version : "",
        (question.current_versions || []).filter(Boolean).length ? Session.text("editor.mod_installed_version") + ": " + question.current_versions.filter(Boolean).join(", ") : "",
        (question.files || []).length ? Session.text("editor.mod_existing_files") + ": " + question.files.join(", ") : ""
    ].filter(Boolean).join("\n") : (question.conflicts || []).map(item => item.required_by.join(", ") + " → " + item.title + " " + item.required + "\n" + Session.text("editor.mod_installed_version") + ": " + item.current.join(", ") + (item.disabled ? "\n" + Session.text("editor.mod_dependency_disabled") : "")).join("\n\n")
    actions: duplicateQuestion ? [
        {key: "replace", text_key: "editor.mod_reinstall", state_key: "primary"},
        ...(question.kind === "duplicate" ? [{key: "both", text_key: "editor.mod_keep_both"}] : []),
        {key: "cancel", text_key: "common.cancel"}
    ] : [
        {key: "install", text_key: "editor.mod_install_required", state_key: "primary"},
        {key: "leave", text_key: "editor.mod_leave_installed"},
        {key: "cancel", text_key: "common.cancel"}
    ]
    cancelAction: "cancel"
    defaultAction: "cancel"
    function answer(choice) {
        const token = requestId
        requestId = ""
        if (token.length)
            Session.resolveModQueue(buildId, token, choice)
    }
    onActionRequested: key => answer(key)
    onCancelled: answer("cancel")
    Component.onDestruction: answer("cancel")
    Connections {
        target: Session
        function onModQueueDecisionDismissed(build, token) {
            if (build === dialog.buildId && token === dialog.requestId) {
                dialog.requestId = ""
                dialog.close()
            }
        }
        function onModQueueDecision(value) {
            if (value.build_id === dialog.buildId && (!value.window_key || value.window_key === dialog.workspaceKey)) {
                dialog.question = value
                dialog.requestId = value.request_id
                dialog.open()
            }
        }
    }
}
