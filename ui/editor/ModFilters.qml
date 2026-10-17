import "../Launcher/Style.js" as Style
import QtQuick
import QtQuick.Layouts
import Working.Gui as UG
import Launcher

Item {
    id: bar
    property string minecraft: ""
    property string loader: ""
    property var categories: []
    property bool catalogue: false
    property string category: ""
    property string sort: ""
    property string channel: ""
    property string contentKind: "mod"
    readonly property var loaderOptions: contentKind === "shader" ? ["iris", "optifine", "canvas"] : contentKind === "resourcepack" ? ["minecraft", "vanilla", "optifine"] : ["fabric", "forge", "neoforge", "quilt"]
    signal apply(string minecraft, string loader, string category, string sort, string channel)
    implicitHeight: Style.value((bar.Window.window ? bar.Window.window.appearance : null), "modFiltersImplicitHeight")
    function reset() { game.text = ""; apply("", "", "", "", "") }
    ColumnLayout {
        id: content
        anchors.fill: parent
        spacing: Style.value((bar.Window.window ? bar.Window.window.appearance : null), "modFiltersSpacing")
        RowLayout {
            Layout.fillWidth: true
            UG.TextField {
                id: game
                tag: "editor.mod_filters.minecraft"
                objectName: "mod.filter.minecraft"
                Layout.fillWidth: true
                text: bar.minecraft
                textKey: "builds.minecraft"
                Accessible.name: Session.text("builds.minecraft")
                onAccepted: bar.apply(text.trim(), bar.loader, bar.category, bar.sort, bar.channel)
            }
            UG.ComboBox {
                tag: "editor.mod_filters.loader"
                objectName: "mod.filter.loader"
                Layout.preferredWidth: Style.value((bar.Window.window ? bar.Window.window.appearance : null), "modFiltersPreferredWidth")
                textRole: "text"
                selectedKey: bar.loader || "__all__"
                model: { Session.revision; return [{key: "__all__", text: Session.text("common.all")}].concat(bar.loaderOptions.map(v => ({key: v, text: v === "neoforge" ? "NeoForge" : v[0].toUpperCase() + v.slice(1)}))) }
                onSelectionRequested: key => bar.apply(game.text.trim(), key === "__all__" ? "" : key, bar.category, bar.sort, bar.channel)
            }
            UG.Button {
                tag: "editor.mod_filters.apply"
                textKey: "editor.apply_filters"
                onClicked: bar.apply(game.text.trim(), bar.loader, bar.category, bar.sort, bar.channel)
            }
            UG.Button {
                tag: "editor.mod_filters.reset"
                objectName: "mod.filter.reset"
                textKey: "editor.reset_filters"
                onClicked: bar.reset()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            UG.ComboBox {
                tag: "editor.mod_filters.category"
                visible: bar.catalogue
                Layout.fillWidth: true
                searchable: true
                textRole: "text"
                selectedKey: bar.category || "__all__"
                model: { Session.revision; return [{key: "__all__", text: Session.text("editor.all_categories"), pinned: true}].concat(bar.categories.map(v => ({key: v, text: v}))) }
                onSelectionRequested: key => bar.apply(game.text.trim(), bar.loader, key === "__all__" ? "" : key, bar.sort, bar.channel)
            }
            UG.ComboBox {
                tag: "editor.mod_filters.sort"
                visible: bar.catalogue
                Layout.fillWidth: true
                textRole: "text"
                selectedKey: bar.sort || "__auto__"
                model: { Session.revision; return ["__auto__", "relevance", "downloads", "follows", "newest", "updated"].map(v => ({key: v, text: Session.text("editor.mod_sort." + v)})) }
                onSelectionRequested: key => bar.apply(game.text.trim(), bar.loader, bar.category, key === "__auto__" ? "" : key, bar.channel)
            }
            UG.ComboBox {
                tag: "editor.mod_filters.channel"
                visible: !bar.catalogue
                Layout.fillWidth: true
                textRole: "text"
                selectedKey: bar.channel || "__all__"
                model: { Session.revision; return [{key: "__all__", text: Session.text("editor.all_channels")}].concat(["release", "beta", "alpha"].map(v => ({key: v, text: v}))) }
                onSelectionRequested: key => bar.apply(game.text.trim(), bar.loader, bar.category, bar.sort, key === "__all__" ? "" : key)
            }
        }
    }
}
