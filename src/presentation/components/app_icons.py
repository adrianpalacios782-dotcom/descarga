"""Iconos vectoriales minimalistas pintados con QPainter para la navegación.

Sin emojis ni dependencias externas: cada icono se dibuja con formas simples
en un QPixmap cuadrado y se devuelve como QIcon.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

ICON_SIZE = 40
_STROKE = 3.0


def _base_pixmap() -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pixmap, painter


def _finish(pixmap: QPixmap, painter: QPainter) -> QIcon:
    painter.end()
    return QIcon(pixmap)


def _pen(color: str) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(_STROKE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def home_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(8.0, 20.0)
    path.lineTo(20.0, 8.0)
    path.lineTo(32.0, 20.0)
    path.moveTo(12.0, 18.0)
    path.lineTo(12.0, 32.0)
    path.lineTo(28.0, 32.0)
    path.lineTo(28.0, 18.0)
    p.drawPath(path)
    return _finish(pixmap, p)


def download_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    p.drawLine(QPointF(20.0, 9.0), QPointF(20.0, 24.0))
    p.drawLine(QPointF(13.5, 17.5), QPointF(20.0, 24.0))
    p.drawLine(QPointF(26.5, 17.5), QPointF(20.0, 24.0))
    tray = QPainterPath()
    tray.moveTo(10.0, 27.0)
    tray.lineTo(10.0, 31.0)
    tray.lineTo(30.0, 31.0)
    tray.lineTo(30.0, 27.0)
    p.drawPath(tray)
    return _finish(pixmap, p)


def history_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    center = QPointF(20.0, 20.0)
    p.drawEllipse(center, 11.0, 11.0)
    p.drawLine(center, QPointF(20.0, 13.5))
    p.drawLine(center, QPointF(25.5, 22.0))
    return _finish(pixmap, p)


def star_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    import math
    cx, cy, r_outer, r_inner = 20.0, 21.0, 11.0, 4.7
    path = QPainterPath()
    for i in range(10):
        radius = r_outer if i % 2 == 0 else r_inner
        angle = -math.pi / 2 + i * math.pi / 5
        point = QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        if i == 0:
            path.moveTo(point)
        else:
            path.lineTo(point)
    path.closeSubpath()
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    return _finish(pixmap, p)


def gear_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(20.0, 20.0), 6.5, 6.5)
    import math
    for i in range(8):
        angle = i * math.pi / 4
        x1 = 20.0 + 9.5 * math.cos(angle)
        y1 = 20.0 + 9.5 * math.sin(angle)
        x2 = 20.0 + 13.0 * math.cos(angle)
        y2 = 20.0 + 13.0 * math.sin(angle)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    return _finish(pixmap, p)


def info_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(20.0, 20.0), 12.0, 12.0)
    dot_pen = _pen(color)
    dot_pen.setWidthF(3.6)
    p.setPen(dot_pen)
    p.drawPoint(QPointF(20.0, 14.5))
    line = QPainterPath()
    line.moveTo(20.0, 19.5)
    line.lineTo(20.0, 27.0)
    p.drawPath(line)
    return _finish(pixmap, p)


def check_icon(color: str = "#1db954", size: int = ICON_SIZE) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setBrush(Qt.BrushStyle.NoBrush)
    circle_pen = QPen(QColor(color))
    circle_pen.setWidthF(size * 0.07)
    p.setPen(circle_pen)
    margin = size * 0.1
    p.drawEllipse(QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
    tick_pen = QPen(QColor(color))
    tick_pen.setWidthF(size * 0.09)
    tick_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    tick_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(tick_pen)
    s = size / ICON_SIZE
    p.drawLine(QPointF(13.0 * s, 20.5 * s), QPointF(18.0 * s, 25.5 * s))
    p.drawLine(QPointF(18.0 * s, 25.5 * s), QPointF(27.5 * s, 15.0 * s))
    p.end()
    return QIcon(pixmap)


NAV_ICONS = {
    0: home_icon,
    1: download_icon,
    2: history_icon,
    3: star_icon,
    4: gear_icon,
    5: info_icon,
}


def _small_pixmap(size: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pixmap, painter


def _thin_pen(color: str, width: float) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def minimize_icon(color: str = "#a4a4ad", size: int = 16) -> QIcon:
    pixmap, p = _small_pixmap(size)
    p.setPen(_thin_pen(color, size * 0.09))
    s = size / ICON_SIZE
    y = 20.0 * s
    p.drawLine(QPointF(12.0 * s, y), QPointF(28.0 * s, y))
    p.end()
    return QIcon(pixmap)


def maximize_icon(color: str = "#a4a4ad", size: int = 16) -> QIcon:
    pixmap, p = _small_pixmap(size)
    p.setPen(_thin_pen(color, size * 0.08))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size / ICON_SIZE
    margin = 11.0 * s
    side = size - 2 * margin
    p.drawRoundedRect(QRectF(margin, margin, side, side), size * 0.12, size * 0.12)
    p.end()
    return QIcon(pixmap)


def restore_icon(color: str = "#a4a4ad", size: int = 16) -> QIcon:
    pixmap, p = _small_pixmap(size)
    p.setPen(_thin_pen(color, size * 0.08))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size / ICON_SIZE
    back = QRectF(11.0 * s, 8.0 * s, 18.0 * s, 18.0 * s)
    front = QRectF(8.0 * s, 11.0 * s, 18.0 * s, 18.0 * s)
    # Rectángulo trasero parcial (dos lados superiores).
    path = QPainterPath()
    path.moveTo(back.left(), back.bottom())
    path.lineTo(back.topLeft())
    path.lineTo(back.topRight())
    path.lineTo(back.right(), back.bottom())
    p.drawPath(path)
    p.drawRect(front)
    p.end()
    return QIcon(pixmap)


def close_icon(color: str = "#a4a4ad", size: int = 16) -> QIcon:
    pixmap, p = _small_pixmap(size)
    p.setPen(_thin_pen(color, size * 0.09))
    s = size / ICON_SIZE
    a, c = 13.0 * s, 27.0 * s
    p.drawLine(QPointF(a, a), QPointF(c, c))
    p.drawLine(QPointF(c, a), QPointF(a, c))
    p.end()
    return QIcon(pixmap)


def clipboard_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(11.0, 9.0, 18.0, 24.0), 3.0, 3.0)
    p.drawPath(clip)
    tab = QPainterPath()
    tab.addRoundedRect(QRectF(15.5, 6.5, 9.0, 6.0), 2.5, 2.5)
    p.drawPath(tab)
    line_pen = _pen(color)
    line_pen.setWidthF(2.2)
    p.setPen(line_pen)
    p.drawLine(QPointF(15.0, 19.0), QPointF(25.0, 19.0))
    p.drawLine(QPointF(15.0, 24.0), QPointF(22.0, 24.0))
    return _finish(pixmap, p)


def link_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    top = QPainterPath()
    top.moveTo(23.5, 10.5)
    top.lineTo(27.0, 7.0)
    arc = QPainterPath()
    arc.moveTo(17.0, 17.0)
    arc.arcTo(QRectF(20.0, 6.0, 14.0, 14.0), 90.0, -180.0)
    p.drawPath(arc)
    bottom_arc = QPainterPath()
    bottom_arc.moveTo(23.0, 23.0)
    bottom_arc.arcTo(QRectF(6.0, 20.0, 14.0, 14.0), 270.0, -180.0)
    p.drawPath(bottom_arc)
    p.drawLine(QPointF(15.0, 25.0), QPointF(25.0, 15.0))
    return _finish(pixmap, p)


def heart_icon(color: str = "#b3b3b3", filled: bool = False) -> QIcon:
    pixmap, p = _base_pixmap()

    cx, cy, r = 20.0, 22.0, 11.5
    path = QPainterPath()
    path.moveTo(cx, cy + r * 0.95)
    path.cubicTo(cx - r * 1.75, cy - r * 0.15, cx - r * 0.55, cy - r * 1.45, cx, cy - r * 0.55)
    path.cubicTo(cx + r * 0.55, cy - r * 1.45, cx + r * 1.75, cy - r * 0.15, cx, cy + r * 0.95)
    path.closeSubpath()
    if filled:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
    else:
        p.setPen(_pen(color))
        p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    return _finish(pixmap, p)


def folder_icon(color: str = "#b3b3b3") -> QIcon:
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    body = QPainterPath()
    body.moveTo(8.0, 30.0)
    body.lineTo(8.0, 12.0)
    body.lineTo(17.0, 12.0)
    body.lineTo(20.0, 16.0)
    body.lineTo(32.0, 16.0)
    body.lineTo(32.0, 30.0)
    body.closeSubpath()
    p.drawPath(body)
    return _finish(pixmap, p)


def search_icon(color: str = "#94a3b8") -> QIcon:
    """Lupa minimalista para la barra de URL del Studio."""
    pixmap, p = _base_pixmap()
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(17.5, 17.5), 7.5, 7.5)
    handle_pen = _pen(color)
    handle_pen.setWidthF(3.4)
    p.setPen(handle_pen)
    p.drawLine(QPointF(23.5, 23.5), QPointF(29.5, 29.5))
    return _finish(pixmap, p)


WINDOW_ICON_SIZE = 16


def window_control_icons() -> dict[str, QIcon]:
    """Crea los iconos de ventana bajo demanda (requiere QApplication activa)."""
    return {
        "minimize": minimize_icon(),
        "maximize": maximize_icon(),
        "restore": restore_icon(),
        "close": close_icon(),
    }
