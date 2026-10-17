from Core.application.diagnostics import diagnostic
from html import escape
from html.parser import HTMLParser
import re
from Core.configuration.settings import DESCRIPTION_CACHE_BYTES, DESCRIPTION_CACHE_ENTRIES
from urllib.parse import urlsplit
from collections import OrderedDict

from markdown_it import MarkdownIt
from PySide6.QtGui import QTextDocument

from Core.presentation.contracts import DescriptionDocument


class SafeHtml(HTMLParser):
    tags = frozenset(("p", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "pre", "code", "em", "strong", "b", "i", "u", "s", "br", "hr", "a", "table", "thead", "tbody", "tr", "th", "td", "del"))
    blocked = frozenset(("script", "style", "iframe", "object", "embed", "svg", "math", "form", "head"))
    void = frozenset(("br", "hr"))

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._blocked: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._blocked:
            if tag in self.blocked:
                self._blocked.append(tag)
            return
        if tag in self.blocked:
            self._blocked.append(tag)
            return
        if tag not in self.tags:
            return
        styles = []
        style = next((value for key, value in attrs if key == "style"), "") or ""
        for rule in style.split(";"):
            name, separator, value = rule.partition(":")
            name, value = name.strip().lower(), value.strip().lower()
            if not separator:
                continue
            allowed = name == "font-weight" and value in ("400", "500", "600", "700", "800", "900", "bold", "normal")
            allowed = allowed or name == "font-style" and value in ("italic", "normal")
            allowed = allowed or name == "text-decoration" and value in ("underline", "line-through", "none")
            allowed = allowed or name in ("color", "background-color") and bool(re.fullmatch(r"#[0-9a-f]{3}(?:[0-9a-f]{3})?", value))
            allowed = allowed or name == "font-family" and value.strip("'\"") in ("monospace", "courier new")
            allowed = allowed or name == "text-align" and value in ("left", "right", "center", "justify")
            if allowed:
                styles.append(name + ":" + value)
        attributes = ' style="' + escape(";".join(styles), quote=True) + '"' if styles else ""
        alignment = next((value for key, value in attrs if key == "align"), "") or ""
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th") and alignment.lower() in ("left", "right", "center", "justify"):
            attributes += ' align="' + alignment.lower() + '"'
        if tag == "a":
            href = next((value for key, value in attrs if key == "href"), None)
            if href:
                try:
                    url = urlsplit(href)
                    if url.scheme.lower() in ("http", "https") and url.hostname and not any(ord(char) < 32 for char in href):
                        attributes += ' href="' + escape(href, quote=True) + '"'
                except ValueError:
                    pass
        self.parts.append("<" + tag + attributes + ">")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._blocked:
            if tag == self._blocked[-1]:
                self._blocked.pop()
            return
        if tag in self.tags and tag not in self.void:
            self.parts.append("</" + tag + ">")

    def handle_data(self, data: str) -> None:
        if not self._blocked:
            self.parts.append(escape(data))


class DescriptionManager:
    def __init__(self) -> None:
        self._mixed_markdown = MarkdownIt("commonmark", {"html": True}).enable(("table", "strikethrough"))
        self._cache = OrderedDict()
        self._cache_bytes = 0

    def handle(self, action: str, payload: object) -> str:
        if action not in ("render", "summary") or not isinstance(payload, DescriptionDocument):
            raise ValueError(diagnostic('descriptions.invalid.description.request'))
        key = (action, payload.format, payload.source)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key][0]
        source = payload.source
        if payload.format == "md":
            document = QTextDocument()
            document.setMarkdown(source, QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML)
            source = document.toHtml()
        elif payload.format == "md_html":
            source = self._mixed_markdown.render(source)
        elif payload.format != "html":
            raise ValueError(diagnostic('descriptions.unknown.description.format'))
        parser = SafeHtml()
        parser.feed(source)
        parser.close()
        result = "".join(parser.parts)
        if action == "summary":
            document = QTextDocument()
            document.setHtml(result)
            result = document.toPlainText().strip()
        size = len(payload.source.encode('utf-8')) + len(result.encode('utf-8'))
        if size <= DESCRIPTION_CACHE_BYTES:
            self._cache[key] = (result, size)
            self._cache_bytes += size
            while self._cache_bytes > DESCRIPTION_CACHE_BYTES or len(self._cache) > DESCRIPTION_CACHE_ENTRIES:
                _, (_, removed) = self._cache.popitem(last=False)
                self._cache_bytes -= removed
        return result

    def close(self) -> None:
        self._cache.clear()
        self._cache_bytes = 0
