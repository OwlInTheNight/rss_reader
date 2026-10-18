"""Отдельное окно для воспроизведения видео."""
from PySide6.QtCore import Signal
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget


class VideoWindow(QWidget):
    closed = Signal()

    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Видеоплеер")
        self.resize(900, 520)
        self.setMinimumSize(480, 270)

        self._video = QVideoWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video)
        player.set_video_output(self._video)

    def present(self, title: str) -> None:
        self.setWindowTitle(f"{title} — Плеер")
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
