"""Панель просмотра статьи и её медиа-вложений."""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QTextBrowser, QVBoxLayout, QWidget)

from ..utils import (ffmpeg_available, format_dt, format_size, is_video_path,
                     yt_dlp_available)


class AttachmentRow(QWidget):
    """Строка одного вложения: значок, имя, размер, кнопки действий."""

    download_requested = Signal(int, bool)  # media_id, только аудио
    play_requested = Signal(int)
    reveal_requested = Signal(int)

    def __init__(self, m: dict, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 3, 0, 3)

        is_video = (
            m.get("kind") == "link"
            or (m.get("mime") or "").lower().startswith("video/")
            or is_video_path(m.get("url") or "")
        )
        icon = QLabel("🎬" if is_video else "🎧")
        icon.setFixedWidth(30)

        name = m.get("file_path") or m.get("url") or "?"
        name = os.path.basename(str(name).split("?")[0]) or str(m.get("url", ""))
        name_lbl = QLabel(name)
        name_lbl.setToolTip(str(m.get("url", "")))

        size = m.get("size")
        size_lbl = QLabel(format_size(size) if size else "")
        size_lbl.setStyleSheet("color: #888;")

        h.addWidget(icon)
        h.addWidget(name_lbl, 1)
        h.addWidget(size_lbl)

        if m.get("file_path"):
            play_text = "▶ Смотреть" if is_video_path(m["file_path"]) else "▶ Слушать"
            b_play = QPushButton(play_text)
            b_play.clicked.connect(
                lambda _=False, mid=m["id"]: self.play_requested.emit(mid)
            )
            b_dir = QPushButton("📁")
            b_dir.setToolTip("Показать в папке")
            b_dir.clicked.connect(
                lambda _=False, mid=m["id"]: self.reveal_requested.emit(mid)
            )
            h.addWidget(b_play)
            h.addWidget(b_dir)
        elif m.get("kind") == "link":
            if yt_dlp_available():
                audio_ext = "mp3" if ffmpeg_available() else "m4a"
                b_video = QPushButton("⬇ Видео")
                b_video.clicked.connect(
                    lambda _=False, mid=m["id"]: self.download_requested.emit(mid, False)
                )
                b_audio = QPushButton(f"⬇ Аудио ({audio_ext})")
                b_audio.clicked.connect(
                    lambda _=False, mid=m["id"]: self.download_requested.emit(mid, True)
                )
                h.addWidget(b_video)
                h.addWidget(b_audio)
            else:
                b = QPushButton("нужен yt-dlp")
                b.setEnabled(False)
                b.setToolTip("Установите: pip install yt-dlp")
                h.addWidget(b)
        else:
            b = QPushButton("⬇ Скачать")
            b.clicked.connect(
                lambda _=False, mid=m["id"]: self.download_requested.emit(mid, False)
            )
            h.addWidget(b)


class ArticleDetails(QWidget):
    """Нижняя половина правой части окна: текст статьи и вложения."""

    open_link_requested = Signal(str)
    download_requested = Signal(int, bool)
    play_requested = Signal(int)
    reveal_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)

        self.title_label = QLabel("Выберите статью")
        self.title_label.setWordWrap(True)
        font = self.title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.title_label.setFont(font)

        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #777;")
        self.meta_label.setWordWrap(True)

        self.link_btn = QPushButton("🔗 Открыть оригинал в браузере")
        self.link_btn.setFlat(True)
        self.link_btn.setStyleSheet("color: #1a6ec8; border: none; text-align: left;")
        self.link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_btn.clicked.connect(
            lambda: self._link and self.open_link_requested.emit(self._link)
        )

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)

        self.media_group = QGroupBox("Вложения (аудио / видео)")
        self.media_layout = QVBoxLayout(self.media_group)
        self.media_layout.setSpacing(2)

        v.addWidget(self.title_label)
        v.addWidget(self.meta_label)
        v.addWidget(self.link_btn, 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(self.browser, 1)
        v.addWidget(self.media_group)

        self._link = None
        self.clear_article()

    def clear_article(self) -> None:
        self._link = None
        self.title_label.setText("Выберите статью в списке")
        self.meta_label.setText("")
        self.link_btn.hide()
        self.browser.setHtml("")
        self._clear_media()
        self.media_group.hide()

    def show_article(self, article: dict, media_rows) -> None:
        self._link = article.get("link")
        self.title_label.setText(article.get("title") or "(без заголовка)")
        parts = [article.get("feed_title") or "", format_dt(article.get("published"))]
        self.meta_label.setText(" · ".join(p for p in parts if p))
        self.link_btn.setVisible(bool(self._link))

        html = article.get("summary") or "<i style='color:#888'>Нет описания</i>"
        self.browser.setHtml(html)

        self._clear_media()
        if media_rows:
            self.media_group.setTitle(f"Вложения ({len(media_rows)})")
            for m in media_rows:
                row = AttachmentRow(m)
                row.download_requested.connect(self.download_requested)
                row.play_requested.connect(self.play_requested)
                row.reveal_requested.connect(self.reveal_requested)
                self.media_layout.addWidget(row)
            self.media_layout.addStretch(1)
            self.media_group.show()
        else:
            self.media_group.hide()

    def _clear_media(self) -> None:
        while self.media_layout.count():
            item = self.media_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
