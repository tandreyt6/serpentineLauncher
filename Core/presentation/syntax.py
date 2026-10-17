import re

from PySide6.QtCore import QObject, Property, Signal
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from shiboken6 import isValid


class SyntaxPainter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
        self.colors = ()
        self.enabled = True

    def highlightBlock(self, text: str) -> None:
        if not self.enabled or len(self.colors) != 3:
            return
        rules = ((r'"(?:[^"\\]|\\.)*"|\b[A-Za-z_][\w.-]*(?=\s*[=:])', self.colors[0]), (r'\b(?:true|false|null|\d+(?:\.\d+)?)\b', self.colors[1]), (r'^\s*\[[^\]]+\]', self.colors[2]))
        for pattern, color in rules:
            formatting = QTextCharFormat()
            formatting.setForeground(QColor(color))
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), formatting)


class ConfigHighlighter(QObject):
    registered = False
    painter_type = SyntaxPainter
    documentChanged = Signal()
    colorsChanged = Signal()
    enabledChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = None
        self._painter = None
        self._colors = []
        self._enabled = True

    def set_document(self, value) -> None:
        if value is self._document:
            return
        if self._painter is not None and isValid(self._painter):
            self._painter.setDocument(None)
            self._painter.deleteLater()
        self._document = value
        self._painter = self.painter_type(value) if value is not None and isValid(value) else None
        if self._painter is not None:
            self._painter.setParent(self)
            self._painter.colors = tuple(self._colors)
            self._painter.enabled = self._enabled
        self.documentChanged.emit()

    def set_colors(self, value) -> None:
        self._colors = list(value)
        if self._painter is not None and isValid(self._painter):
            self._painter.colors = tuple(self._colors)
            self._painter.rehighlight()
        self.colorsChanged.emit()

    document = Property(QObject, lambda self: self._document, set_document, notify=documentChanged)
    colors = Property("QVariantList", lambda self: self._colors, set_colors, notify=colorsChanged)

    def set_enabled(self, value: bool) -> None:
        self._enabled = value
        if self._painter is not None and isValid(self._painter):
            self._painter.enabled = value
            self._painter.rehighlight()
        self.enabledChanged.emit()

    enabled = Property(bool, lambda self: self._enabled, set_enabled, notify=enabledChanged)


class LogSyntaxPainter(SyntaxPainter):
    headers = re.compile(r'^\[[^\]]+\](?:\s*\[[^\]]+\])*')
    levels = re.compile(r'\[(?:[^\[\]\n]*/)?(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\]|\blevel=[\"\x27](TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)[\"\x27]')
    timestamp = re.compile(r'^\[\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\]')
    xml_tags = re.compile(r'</?(?:log4j:)?[A-Za-z_][\w:.-]*(?:\s[^>]*?)?/?>')
    exceptions = re.compile(r'\b[\w.$]*(?:Exception|Error)\b')
    roles = {'TRACE': 0, 'DEBUG': 0, 'INFO': 2, 'WARN': 3, 'WARNING': 3, 'ERROR': 4, 'FATAL': 4}

    def highlightBlock(self, text):
        if not self.enabled or len(self.colors) != 5:
            return
        def paint(start, end, role, bold=False):
            formatting = QTextCharFormat()
            formatting.setForeground(QColor(self.colors[role]))
            if bold:
                formatting.setFontWeight(QFont.Weight.DemiBold)
            begin = len(text[:start].encode('utf-16-le')) // 2
            length = len(text[start:end].encode('utf-16-le')) // 2
            self.setFormat(begin, length, formatting)
        levels = list(self.levels.finditer(text))
        role = self.roles[next(value for value in levels[0].groups() if value)] if levels else self.previousBlockState()
        self.setCurrentBlockState(role if role >= 0 else 2)
        continuation = text.lstrip().startswith(('at ', 'Caused by:', 'Suppressed:', '... '))
        if levels or continuation:
            paint(0, len(text), role if role >= 0 else 2)
        header = self.headers.match(text)
        if header:
            paint(*header.span(), 1)
        stamp = self.timestamp.match(text)
        if stamp:
            paint(*stamp.span(), 0)
        for tag in self.xml_tags.finditer(text):
            paint(*tag.span(), 1)
        for match in levels:
            value = next(value for value in match.groups() if value)
            paint(*match.span(), self.roles[value], True)
        for exception in self.exceptions.finditer(text):
            paint(*exception.span(), 4)


class LogHighlighter(ConfigHighlighter):
    registered = False
    painter_type = LogSyntaxPainter
