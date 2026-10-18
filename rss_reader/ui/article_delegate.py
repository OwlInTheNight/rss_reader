"""Современное отображение статьи в списке: две строки + точка непрочитанного."""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from ..theme import theme_colors

DATA_ROLE = Qt.ItemDataRole.UserRole + 1


class ArticleDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = theme_colors("light")

    def set_colors(self, colors: dict) -> None:
        self._colors = colors

    def sizeHint(self, option, index):
        return QSize(option.rect.width() or 260, 58)

    def paint(self, painter: QPainter, option, index):
        data = index.data(DATA_ROLE) or {}
        c = self._colors
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        card = QRectF(option.rect).adjusted(4, 3, -4, -3)
        selected = bool(option.state & QStyle.State.State_Selected)
        hovered = bool(option.state & QStyle.State.State_MouseOver)
        if selected or hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c["selection"] if selected else c["hover"]))
            painter.drawRoundedRect(card, 7, 7)

        unread = not data.get("is_read", False)

        title_font = QFont(option.font)
        title_font.setBold(unread)
        title_fm = QFontMetrics(title_font)
        meta_font = QFont(option.font)
        meta_font.setBold(False)
        meta_font.setPointSizeF(max(8.5, option.font.pointSizeF() * 0.85))
        meta_fm = QFontMetrics(meta_font)

        title_x = card.left() + (26 if unread else 12)
        title_w = card.width() - (26 if unread else 12) - 10
        title_y = int(card.top() + 8)
        meta_y = title_y + title_fm.height() + 3

        if unread:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c["accent"]))
            dot_cy = title_y + title_fm.height() / 2
            painter.drawEllipse(QRectF(card.left() + 10, dot_cy - 4, 8, 8))

        title = title_fm.elidedText(data.get("title") or "(без заголовка)",
                                    Qt.TextElideMode.ElideRight, int(title_w))
        painter.setPen(QColor(c["text"]))
        painter.setFont(title_font)
        painter.drawText(QRectF(title_x, title_y, title_w, title_fm.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)

        painter.setPen(QColor(c["secondary"]))
        painter.setFont(meta_font)
        painter.drawText(QRectF(card.left() + 12, meta_y, card.width() - 24, meta_fm.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         data.get("meta_line") or "")

        painter.restore()
