from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from Core.configuration.settings import SHORTCUT_ACTIONS, SHORTCUT_RESERVED
from Core.application.shortcuts import conflicts


def from_key(key, modifiers):
    if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr):
        return ''
    if key == Qt.Key_Backtab:
        key = Qt.Key_Tab
        modifiers |= Qt.ShiftModifier.value
    if key == Qt.Key_Enter:
        key = Qt.Key_Return
    modifiers &= (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier | Qt.MetaModifier).value
    return QKeySequence(key | modifiers).toString(QKeySequence.PortableText)


def check(settings, action, text):
    if action not in {entry[0] for entry in SHORTCUT_ACTIONS}:
        return dict(valid=False, sequence='', conflicts=[], error='shortcuts.invalid')
    if not text:
        return dict(valid=True, sequence='', conflicts=[], error='')
    sequence = QKeySequence.fromString(text, QKeySequence.PortableText)
    canonical = sequence.toString(QKeySequence.PortableText)
    if canonical.endswith('Enter'):
        canonical = canonical[:-5] + 'Return'
        sequence = QKeySequence.fromString(canonical, QKeySequence.PortableText)
    valid = sequence.count() == 1 and not sequence.isEmpty() and bool(canonical)
    if valid:
        stroke = sequence[0]
        key = stroke.key()
        modified = bool(stroke.keyboardModifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
        valid = key != Qt.Key_unknown and (modified or Qt.Key_F1 <= key <= Qt.Key_F35)
    if not valid:
        return dict(valid=False, sequence=canonical, conflicts=[], error='shortcuts.invalid')
    if canonical in SHORTCUT_RESERVED:
        return dict(valid=False, sequence=canonical, conflicts=[], error='shortcuts.reserved')
    occupied = conflicts(settings, action, canonical)
    return dict(valid=not occupied, sequence=canonical, conflicts=occupied,
                error='shortcuts.conflict' if occupied else '')


def label(text):
    return QKeySequence.fromString(text, QKeySequence.PortableText).toString(QKeySequence.NativeText)
