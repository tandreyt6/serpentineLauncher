function normalize(text) {
    return String(text).toLowerCase().replace(/ё/g, "е").trim()
}

function keyboardVariant(text) {
    const latin = "qwertyuiop[]asdfghjkl;'zxcvbnm,.`"
    const cyrillic = "йцукенгшщзхъфывапролджэячсмитьбюё"
    return text.split("").map(function (letter) {
        const index = latin.indexOf(letter)
        if (index >= 0)
            return cyrillic[index]
        const reverse = cyrillic.indexOf(letter)
        return reverse >= 0 ? latin[reverse] : letter
    }).join("")
}

function score(entry, query) {
    const title = normalize(entry.title)
    const haystack = normalize(entry.title + " " + entry.detail + " " + entry.key)
    if (title === query)
        return 0
    if (title.startsWith(query))
        return 1
    if (title.indexOf(query) >= 0)
        return 2
    const words = query.split(/\s+/)
    if (words.every(word => haystack.indexOf(word) >= 0))
        return 3
    return -1
}

function find(entries, text) {
    const query = normalize(text)
    if (!query.length)
        return entries
    const alternative = normalize(keyboardVariant(query))
    return entries.map(function (entry, index) {
        const direct = score(entry, query)
        const alternate = score(entry, alternative)
        const rank = direct >= 0 ? direct : alternate >= 0 ? 4 + alternate : -1
        return {entry: entry, rank: rank, index: index}
    }).filter(match => match.rank >= 0)
      .sort((first, second) => first.rank - second.rank || first.index - second.index)
      .map(match => match.entry)
}
