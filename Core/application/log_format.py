from datetime import datetime
import re
from xml.etree import ElementTree


_EVENT_TOKEN = re.compile(r'<!\[CDATA\[.*?(?:\]\]>|\Z)|(?P<open><(?P<tag>(?:[A-Za-z_][\w.-]*:)?Event)\b[^>]*>)|(?P<close></(?:[A-Za-z_][\w.-]*:)?Event\s*>)', re.DOTALL)
_LOG_XML = re.compile(r'</?(?:[A-Za-z_][\w.-]*:)?(?:Event|Message|Throwable|EventSet)\b')
_ENVELOPE = re.compile(r'<\?xml\b.*?\?>|</?(?:[A-Za-z_][\w.-]*:)?EventSet\b[^>]*>', re.DOTALL)
_PARTIAL = re.compile(r'</?(?:[A-Za-z_][\w.-]*:)?(?:Event|Message|Throwable)\b[^>]*>')
_ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))')


def _outside(text):
    return _PARTIAL.sub('', _ENVELOPE.sub('', text)).replace('<![CDATA[', '').replace(']]>', '').strip('\r\n')


def _event(fragment, tag):
    prefix = tag.split(':')[0] if ':' in tag else ''
    namespace = f' xmlns:{prefix}="urn:launcher:log4j"' if prefix else ''
    try:
        event = ElementTree.fromstring(f'<events{namespace}>' + fragment + '</events>')[0]
    except ElementTree.ParseError:
        return _outside(fragment)
    attributes = event.attrib
    stamp = attributes.get('timestamp', '')
    try:
        milliseconds = int(stamp)
        stamp = datetime.fromtimestamp(milliseconds / 1000).strftime('%H:%M:%S') + f'.{milliseconds % 1000:03}'
    except (ValueError, OverflowError, OSError):
        pass
    level = attributes.get('level', '').upper()
    context = '/'.join(value for value in (attributes.get('thread', ''), attributes.get('logger', '')) if value)
    header = ' '.join('[' + value.replace('\r', ' ').replace('\n', ' ') + ']' for value in (stamp, level, context) if value)
    messages = [''.join(child.itertext()).strip('\r\n') for child in event if child.tag.rsplit('}', 1)[-1] in ('Message', 'Throwable')]
    message = '\n'.join(messages)
    return (header + (' ' if header and message else '') + message).rstrip('\r\n')


def format_log(text, check=None):
    text = _ANSI.sub('', text)
    if not _LOG_XML.search(text):
        return text
    lines = []
    position = 0
    opening = None
    for token in _EVENT_TOKEN.finditer(text):
        if check is not None:
            check()
        if token.group('open'):
            outside = _outside(text[position:token.start()])
            if outside.strip():
                lines.append(outside)
            opening = token
            position = token.start()
        elif token.group('close') and opening is not None:
            lines.append(_event(text[opening.start():token.end()], opening.group('tag')))
            position = token.end()
            opening = None
    outside = _outside(text[position:])
    if outside.strip():
        lines.append(outside)
    result = '\n'.join(lines)
    return result + ('\n' if result and text.endswith(('\n', '\r')) else '')
