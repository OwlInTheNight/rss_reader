"""Нижняя панель плеера: управление воспроизведением."""
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QSlider, QStyle, QWidget)


def _fmt(ms: int) -> str:
    if ms is None or ms < 0:
        ms = 0
    total = int(ms // 1000)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class PlayerBar(QWidget):
    seek_requested = Signal(int)
    toggle_requested = Signal()
    stop_requested = Signal()
    volume_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self._duration = 0

        h = QHBoxLayout(self)
        h.setContentsMargins(8, 6, 8, 6)

        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(44, 36)
        self._set_icon(False)
        self.play_btn.clicked.connect(self.toggle_requested.emit)

        self.stop_btn = QPushButton()
        self.stop_btn.setFixedSize(44, 36)
        self.stop_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        )
        self.stop_btn.clicked.connect(self.stop_requested.emit)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setSingleStep(1000)
        self.slider.setPageStep(10000)
        self.slider.sliderReleased.connect(self._on_seek)

        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setMinimumWidth(110)
        self.time_lbl.setProperty("role", "secondary")

        self.track_lbl = QLabel("")
        self.track_lbl.setProperty("role", "secondary")
        self.track_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        vol_icon = QLabel("🔊")
        vol_icon.setProperty("role", "secondary")
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(80)
        self.vol.setFixedWidth(100)
        self.vol.valueChanged.connect(self.volume_changed.emit)

        h.addWidget(self.play_btn)
        h.addWidget(self.stop_btn)
        h.addWidget(self.slider, 2)
        h.addWidget(self.time_lbl)
        h.addStretch(1)
        h.addWidget(self.track_lbl, 3)
        h.addWidget(vol_icon)
        h.addWidget(self.vol)

    def _set_icon(self, playing: bool) -> None:
        pixmap = (QStyle.StandardPixmap.SP_MediaPause if playing
                  else QStyle.StandardPixmap.SP_MediaPlay)
        self.play_btn.setIcon(self.style().standardIcon(pixmap))

    def _on_seek(self) -> None:
        self.seek_requested.emit(self.slider.value())

    # ------------------------------------------------------------ слоты
    @Slot(bool)
    def set_playing(self, playing: bool) -> None:
        self._set_icon(playing)

    def set_duration(self, ms: int) -> None:
        self._duration = int(ms)
        self.slider.setRange(0, self._duration)
        self._update_time(self.slider.value())

    def set_position(self, ms: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(int(ms))
            self._update_time(int(ms))

    def set_track(self, text: str) -> None:
        self.track_lbl.setText(text or "")
        self.track_lbl.setToolTip(text or "")

    def _update_time(self, pos: int) -> None:
        self.time_lbl.setText(f"{_fmt(pos)} / {_fmt(self._duration)}")
