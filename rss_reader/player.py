"""Обёртка над QMediaPlayer: аудио и локальное видео."""
import os

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class Player(QObject):
    position_changed = Signal(int)
    duration_changed = Signal(int)
    playing_changed = Signal(bool)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.8)
        self._player.setAudioOutput(self._audio)

        self._player.positionChanged.connect(self.position_changed)
        self._player.durationChanged.connect(self.duration_changed)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(
            lambda _err, msg: self.error_occurred.emit(msg)
        )

    def _on_state(self, state):
        self.playing_changed.emit(state == QMediaPlayer.PlaybackState.PlayingState)

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()

    # -------------------------------------------------------------- API
    def set_video_output(self, widget) -> None:
        self._player.setVideoOutput(widget)

    def play_file(self, path: str) -> None:
        self._player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
        self._player.play()

    def toggle(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def stop(self) -> None:
        self._player.stop()

    def seek(self, ms: int) -> None:
        self._player.setPosition(int(ms))

    def set_volume(self, value: int) -> None:
        self._audio.setVolume(max(0.0, min(1.0, value / 100.0)))
