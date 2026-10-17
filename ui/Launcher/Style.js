function value(style, key) {
    if (style && style[key] !== undefined)
        return style[key]
    if (UiDefaults[key] === undefined)
        throw new Error(key)
    return UiDefaults[key]
}
