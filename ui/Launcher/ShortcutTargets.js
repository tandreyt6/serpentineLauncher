function dispatch(root, action) {
    if (!root || !root.visible || !root.enabled)
        return false
    if (typeof root.handleShortcut === "function" && root.handleShortcut(action))
        return true
    if (root.shortcutBoundary === true)
        return false
    const children = root.children || []
    for (let i = children.length - 1; i >= 0; --i) {
        if (dispatch(children[i], action))
            return true
    }
    return false
}
