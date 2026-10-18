"""Генерация иконки приложения (assets/app.ico).

Рисует скруглённый квадрат с сине-фиолетовым градиентом и белым
RSS-символом. Запуск: python scripts/make_icon.py
"""
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QIcon, QImage,
                           QLinearGradient, QPainter, QPen)
from PySide6.QtWidgets import QApplication  # noqa: F401

SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # фон: скруглённый квадрат с градиентом
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#5B8CFF"))
    grad.setColorAt(1.0, QColor("#8A5CFF"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    margin = size * 0.03
    p.drawRoundedRect(QRectF(margin, margin, size - 2 * margin, size - 2 * margin),
                      size * 0.22, size * 0.22)

    # RSS-символ: точка и две дуги из левого нижнего угла
    cx, cy = size * 0.32, size * 0.68
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(QPointF(cx, cy), size * 0.07, size * 0.07)

    pen = QPen(QColor("#FFFFFF"), size * 0.075)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(pen)
    for radius in (0.21, 0.35):
        d = size * radius
        p.drawArc(QRectF(cx - d, cy - d, 2 * d, 2 * d), 0, 90 * 16)
    p.end()
    return img


def to_png(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def write_ico(pngs, path: Path) -> None:
    n = len(pngs)
    header = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    entries = b""
    blobs = b""
    for size, data in pngs:
        side = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32,
                               len(data), offset + len(blobs))
        blobs += data
    path.write_bytes(header + entries + blobs)


def main() -> None:
    app = QGuiApplication([])  # noqa: F841 — нужен для QPainter/QImage
    out = Path(__file__).resolve().parents[1] / "assets" / "app.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    pngs = [(s, to_png(render(s))) for s in SIZES]
    write_ico(pngs, out)
    print("saved:", out)


if __name__ == "__main__":
    main()
