import QtQuick

Loader {
    required property string viewKey
    asynchronous: true
    source: ThemeUI.viewUrl(viewKey)
    onStatusChanged: if (status === Loader.Error) ThemeUI.mainFailed(UiDiagnostics["qml.main_failed"])
}
