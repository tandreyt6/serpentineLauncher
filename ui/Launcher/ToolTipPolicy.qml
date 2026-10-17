import "Style.js" as Style
import QtQuick
import QtQuick.Controls as QC

Item {
    id: policy
    visible: false
    readonly property var sharedTip: policy.QC.ToolTip.toolTip
    readonly property var tipOwner: sharedTip.parent
    TextMetrics {
        id: labelMetrics
        text: policy.sharedTip.text
        font.family: policy.tipOwner && policy.tipOwner.appearance ? policy.tipOwner.appearance.fontFamily : policy.tipOwner && policy.tipOwner.font ? policy.tipOwner.font.family : policy.sharedTip.font.family
        font.pixelSize: policy.tipOwner && policy.tipOwner.appearance ? policy.tipOwner.appearance.fontSize : policy.tipOwner && policy.tipOwner.font ? policy.tipOwner.font.pixelSize : Style.value((policy.Window.window ? policy.Window.window.appearance : null), "toolTipPolicyPixelSize")
    }
    function redundant(tip) {
        const owner = tip.parent
        if (!owner || !owner.enabled)
            return false
        if (owner.contentItem && owner.contentItem.truncated === true
            || typeof owner.availableWidth === "number" && owner.availableWidth > 0 && labelMetrics.advanceWidth > owner.availableWidth)
            return false
        const text = String(tip.text || "").trim()

        if (owner.hideText === true && owner.componentType !== "ComboBoxOption")
            return false
        return text.length > 0 && (typeof owner.text === "string" && text === owner.text.trim()
            || typeof owner.displayText === "string" && text === owner.displayText.trim())
    }
    Connections {
        target: policy.sharedTip
        function suppressDuplicate() {
            if (policy.enabled && target.visible && policy.redundant(target))
                target.close()
        }
        function onVisibleChanged() { suppressDuplicate() }
        function onTextChanged() { suppressDuplicate() }
        function onParentChanged() { suppressDuplicate() }
    }
}
