from PySide6.QtCore import QPoint, QRect, QSize


def offset_position(reference: QRect, size: QSize, available: QRect, offset: int) -> QPoint:
    def coordinate(origin, minimum, maximum):
        maximum = max(minimum, maximum)
        if minimum <= origin + offset <= maximum:
            return origin + offset
        if minimum <= origin - offset <= maximum:
            return origin - offset
        return min(maximum, max(minimum, origin + offset))

    return QPoint(
        coordinate(reference.x(), available.x(), available.x() + available.width() - size.width()),
        coordinate(reference.y(), available.y(), available.y() + available.height() - size.height()),
    )
