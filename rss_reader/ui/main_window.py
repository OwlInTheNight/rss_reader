"""Главное окно приложения."""
import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (QFileDialog, QInputDialog, QLineEdit, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu,
                               QMessageBox, QSplitter, QStackedWidget, QToolBar,
                               QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..db import Database
from ..download_manager import DownloadManager, DownloadTask
from ..feed_worker import RefreshWorker
from ..player import Player
from ..utils import (default_db_path, default_downloads_dir, ext_from_mime,
                     ext_from_url, format_dt, is_video_path, sanitize_filename,
                     seed_default_feeds)
from .details import ArticleDetails
from .downloads_panel import DownloadsPanel
from .player_bar import PlayerBar
from .video_window import VideoWindow

ROLE = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — RSS-читалка с медиа")
        self.resize(1240, 800)

        self.db = Database(default_db_path())
        seed_default_feeds(self.db)
        saved = self.db.get_setting("download_dir")
        self.dl_dir = Path(saved) if saved else Path(default_downloads_dir())

        self.current_feed = None
        self._current_article_id = None
        self._refresh_worker = None
        self._video_window = None
        self._rebuilding = False

        self._font_bold = QFont(self.font())
        self._font_bold.setBold(True)

        self.player = Player(self)
        self.manager = DownloadManager(self)

        self._build_ui()
        self._connect_signals()

        self.rebuild_feed_list()
        if self.feed_list.currentRow() < 0:
            self.feed_list.setCurrentRow(0)

        if not os.environ.get("RSSREADER_NO_REFRESH"):
            QTimer.singleShot(200, self.refresh_all)

    # ================================================================ UI
    def _build_ui(self):
        self._build_menu()

        toolbar = QToolBar("Главная", self)
        toolbar.setMovable(False)
        act_add = QAction("➕ Добавить ленту", self)
        act_add.setShortcut("Ctrl+N")
        act_add.triggered.connect(self.add_feed_dialog)
        act_ref = QAction("⟳ Обновить все", self)
        act_ref.setShortcut("F5")
        act_ref.triggered.connect(lambda: self.refresh_all())
        toolbar.addAction(act_add)
        toolbar.addAction(act_ref)
        self.addToolBar(toolbar)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        side = QWidget()
        side_v = QVBoxLayout(side)
        side_v.setContentsMargins(0, 0, 0, 0)
        cap = QLabel("ЛЕНТЫ")
        cap.setStyleSheet("color: #777; font-size: 11px; font-weight: bold;")
        side_v.addWidget(cap)
        self.feed_list = QListWidget()
        self.feed_list.setMinimumWidth(210)
        self.feed_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.feed_list.currentItemChanged.connect(self._on_feed_changed)
        self.feed_list.customContextMenuRequested.connect(self._feed_context_menu)
        side_v.addWidget(self.feed_list)
        splitter.addWidget(side)

        self.stack = QStackedWidget()
        self.article_list = QListWidget()
        self.article_list.currentItemChanged.connect(self._on_article_changed)
        self.article_list.itemDoubleClicked.connect(self._open_selected_in_browser)
        self.details = ArticleDetails()
        self.art_split = QSplitter(Qt.Orientation.Vertical)
        self.art_split.addWidget(self.article_list)
        self.art_split.addWidget(self.details)
        self.art_split.setSizes([420, 320])
        self.downloads_panel = DownloadsPanel()
        self.stack.addWidget(self.art_split)
        self.stack.addWidget(self.downloads_panel)
        splitter.addWidget(self.stack)
        splitter.setSizes([260, 960])

        self.player_bar = PlayerBar()

        root.addWidget(splitter, 1)
        root.addWidget(self.player_bar)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Готово")

    def _build_menu(self):
        m_feeds = self.menuBar().addMenu("&Ленты")
        a_add = QAction("Добавить ленту…", self)
        a_add.setShortcut("Ctrl+N")
        a_add.triggered.connect(self.add_feed_dialog)
        m_feeds.addAction(a_add)
        a_ref = QAction("Обновить все ленты", self)
        a_ref.setShortcut("F5")
        a_ref.triggered.connect(lambda: self.refresh_all())
        m_feeds.addAction(a_ref)
        m_feeds.addSeparator()
        a_quit = QAction("Выход", self)
        a_quit.triggered.connect(self.close)
        m_feeds.addAction(a_quit)

        m_media = self.menuBar().addMenu("&Медиа")
        a_dir = QAction("Открыть папку загрузок", self)
        a_dir.triggered.connect(self.open_downloads_folder)
        m_media.addAction(a_dir)
        a_set = QAction("Изменить папку загрузок…", self)
        a_set.triggered.connect(self.choose_downloads_folder)
        m_media.addAction(a_set)

        m_help = self.menuBar().addMenu("&Справка")
        a_about = QAction("О программе", self)
        a_about.triggered.connect(self._show_about)
        m_help.addAction(a_about)

    def _connect_signals(self):
        # плеер
        pb = self.player_bar
        pb.toggle_requested.connect(self.player.toggle)
        pb.stop_requested.connect(self.player.stop)
        pb.seek_requested.connect(self.player.seek)
        pb.volume_changed.connect(self.player.set_volume)
        self.player.position_changed.connect(pb.set_position)
        self.player.duration_changed.connect(pb.set_duration)
        self.player.playing_changed.connect(pb.set_playing)
        self.player.error_occurred.connect(
            lambda msg: self.statusBar().showMessage(f"Плеер: {msg}", 8000)
        )

        # статья
        d = self.details
        d.open_link_requested.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        d.download_requested.connect(self.start_download)
        d.play_requested.connect(self.play_media)
        d.reveal_requested.connect(self.reveal_path)

        # загрузки
        p = self.downloads_panel
        p.play_requested.connect(self.play_media)
        p.reveal_requested.connect(self.reveal_media)
        p.delete_requested.connect(self.delete_download)
        p.cancel_requested.connect(self.manager.cancel)
        p.open_folder_requested.connect(self.open_downloads_folder)
        self.manager.progress.connect(self.downloads_panel.update_progress)
        self.manager.finished.connect(self._on_download_finished)
        self.manager.failed.connect(self._on_download_failed)

    # ========================================================== ленты
    def rebuild_feed_list(self):
        self._rebuilding = True
        try:
            counts = self.db.feed_counts()
            current = self.feed_list.currentItem()
            current_data = current.data(ROLE) if current else None

            self.feed_list.clear()
            it = QListWidgetItem("📰 Все статьи")
            it.setData(ROLE, ("all", None))
            self.feed_list.addItem(it)
            it = QListWidgetItem("⬇ Загрузки")
            it.setData(ROLE, ("dl", None))
            self.feed_list.addItem(it)

            head = QListWidgetItem("— ЛЕНТЫ —")
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            head.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            head.setForeground(QBrush(QColor("#999")))
            head.setFont(self._font_bold)
            self.feed_list.addItem(head)

            for feed in self.db.list_feeds():
                n = counts.get(feed["id"], 0)
                it = QListWidgetItem(f"{feed['title']}  ({n})")
                it.setToolTip(feed["url"])
                it.setData(ROLE, ("feed", feed["id"]))
                self.feed_list.addItem(it)

            target = 0
            if current_data:
                for i in range(self.feed_list.count()):
                    if self.feed_list.item(i).data(ROLE) == current_data:
                        target = i
                        break
            self.feed_list.setCurrentRow(target)
        finally:
            self._rebuilding = False
        self._apply_feed_selection()

    def _on_feed_changed(self, current, _previous):
        if self._rebuilding:
            return
        self._apply_feed_selection()

    def _apply_feed_selection(self):
        item = self.feed_list.currentItem()
        if not item:
            return
        mode, fid = item.data(ROLE)
        if mode == "dl":
            self.stack.setCurrentIndex(1)
            self.reload_downloads()
        else:
            self.stack.setCurrentIndex(0)
            self.current_feed = fid if mode == "feed" else None
            self.reload_articles()

    def _feed_context_menu(self, pos):
        item = self.feed_list.itemAt(pos)
        if not item:
            return
        data = item.data(ROLE)
        if not data or data[0] != "feed":
            return
        menu = QMenu(self)
        a_ref = menu.addAction("Обновить эту ленту")
        a_del = menu.addAction("Удалить ленту…")
        chosen = menu.exec(self.feed_list.mapToGlobal(pos))
        if chosen == a_ref:
            feed = self.db.feed(data[1])
            if feed:
                self.refresh_all([feed])
        elif chosen == a_del:
            self._delete_feed(data[1])

    def _delete_feed(self, feed_id):
        feed = self.db.feed(feed_id)
        if not feed:
            return
        ans = QMessageBox.question(
            self, "Удаление ленты",
            f"Удалить ленту «{feed['title']}»?\nСкачанные файлы останутся на диске.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_feed(feed_id)
        if self.current_feed == feed_id:
            self.current_feed = None
        self.rebuild_feed_list()
        if self.stack.currentIndex() == 0:
            self.reload_articles()

    def add_feed_dialog(self):
        url, ok = QInputDialog.getText(
            self, "Добавить ленту", "URL RSS-ленты:",
            QLineEdit.EchoMode.Normal, "https://",
        )
        if not ok:
            return
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(
                self, "Добавление ленты",
                "Нужен корректный URL, начинающийся с http:// или https://",
            )
            return
        feed_id = self.db.add_feed(url)
        if feed_id is None:
            QMessageBox.information(self, "Добавление ленты", "Такая лента уже есть в списке.")
            return
        self.rebuild_feed_list()
        for i in range(self.feed_list.count()):
            if self.feed_list.item(i).data(ROLE) == ("feed", feed_id):
                self.feed_list.setCurrentRow(i)
                break
        feed = self.db.feed(feed_id)
        if feed:
            self.refresh_all([feed])

    def refresh_all(self, feeds=None):
        if self._refresh_worker is not None:
            try:
                if self._refresh_worker.isRunning():
                    self.statusBar().showMessage("Обновление уже выполняется…", 3000)
                    return
            except RuntimeError:
                pass
        feeds = feeds or self.db.list_feeds()
        if not feeds:
            self.statusBar().showMessage(
                "Нет лент — добавьте первую через «➕ Добавить ленту»", 6000
            )
            return
        self.statusBar().showMessage("Обновление лент…")
        worker = RefreshWorker(self.db.path, feeds)
        worker.feed_done.connect(self._on_feed_done)
        worker.feed_error.connect(
            lambda title, err: self.statusBar().showMessage(
                f"Ошибка: {title}: {err}", 8000
            )
        )
        worker.all_done.connect(
            lambda: self.statusBar().showMessage("Ленты обновлены", 5000)
        )
        self._refresh_worker = worker
        worker.start()

    def _on_feed_done(self, feed_id, fresh):
        self.rebuild_feed_list()
        current = self.feed_list.currentItem()
        mode, fid = (current.data(ROLE) if current else ("all", None))
        if (self.stack.currentIndex() == 0 and fid in (None, feed_id)
                and self.article_list.currentRow() < 0):
            self.reload_articles()
        elif fresh:
            self.statusBar().showMessage(f"Новых статей: {fresh}", 5000)

    # ======================================================== статьи
    def reload_articles(self):
        rows = self.db.articles(self.current_feed)
        self.article_list.clear()
        for r in rows:
            label = r["title"] or "(без заголовка)"
            if self.current_feed is None and r["feed_title"]:
                label = f"[{r['feed_title']}]  {label}"
            it = QListWidgetItem(label)
            tip = format_dt(r["published"])
            if r["feed_title"]:
                tip = (tip + "\n" if tip else "") + r["feed_title"]
            it.setToolTip(tip)
            if not r["is_read"]:
                it.setFont(self._font_bold)
            it.setData(ROLE, r["id"])
            self.article_list.addItem(it)
        self._current_article_id = None
        self.details.clear_article()
        if rows:
            self.statusBar().showMessage(f"Статей: {len(rows)}", 4000)

    def _on_article_changed(self, current, _previous):
        if current is None:
            return
        article_id = current.data(ROLE)
        row = self.db.article(article_id)
        if not row:
            return
        self._current_article_id = article_id
        if not row["is_read"]:
            self.db.set_read(article_id)
            current.setFont(self.font())
        media = self.db.media_for_article(article_id)
        self.details.show_article(row, media)

    def _open_selected_in_browser(self, item):
        row = self.db.article(item.data(ROLE))
        if row and row["link"]:
            QDesktopServices.openUrl(QUrl(row["link"]))

    # ======================================================= загрузки
    def reload_downloads(self):
        self.downloads_panel.reload_items(self.db.downloaded_media())

    def start_download(self, media_id, audio_only=False):
        row = self.db.media(media_id)
        if not row:
            return
        if row["file_path"]:
            self.reveal_path(row["file_path"])
            return
        dest = os.path.join(
            str(self.dl_dir), sanitize_filename(row["feed_title"] or "Медиа")
        )
        os.makedirs(dest, exist_ok=True)
        if row["kind"] == "link":
            name = ""
        else:
            ext = ext_from_url(row["url"]) or ext_from_mime(row["mime"]) or "bin"
            name = sanitize_filename(row["article_title"] or "media") + "." + ext
        task = DownloadTask(
            media_id=row["id"], url=row["url"], kind=row["kind"],
            dest_dir=dest, name=name, audio_only=audio_only,
        )
        self.manager.enqueue(task)
        shown = name or os.path.basename(row["url"].split("?")[0]) or row["url"]
        self.downloads_panel.add_active(row["id"], shown)
        if self.feed_list.currentRow() != 1:
            self.feed_list.setCurrentRow(1)
        else:
            self.reload_downloads()
        self.statusBar().showMessage(f"Скачивается: {shown}")

    def _on_download_finished(self, media_id, path):
        self.db.set_media_downloaded(media_id, path)
        self.downloads_panel.finish_active(media_id)
        if self.stack.currentIndex() == 1:
            self.reload_downloads()
        row = self.db.media(media_id)
        if row and self._current_article_id and row["article_id"] == self._current_article_id:
            article = self.db.article(self._current_article_id)
            if article:
                media = self.db.media_for_article(self._current_article_id)
                self.details.show_article(article, media)
        self.statusBar().showMessage(f"Скачано: {os.path.basename(path)}", 6000)

    def _on_download_failed(self, media_id, err):
        self.downloads_panel.fail_active(media_id)
        msg = "Загрузка отменена" if err == "Отменено" else f"Ошибка загрузки: {err}"
        self.statusBar().showMessage(msg, 8000)

    # ========================================================= плеер
    def play_media(self, media_id):
        row = self.db.media(media_id)
        if not row:
            return
        path = row["file_path"]
        if not path:
            QMessageBox.information(self, "Плеер", "Сначала скачайте файл.")
            return
        if not os.path.exists(path):
            QMessageBox.warning(self, "Плеер", f"Файл не найден:\n{path}")
            return
        if is_video_path(path):
            self._ensure_video_window().present(os.path.basename(path))
        track = f"{row['article_title'] or ''} — {os.path.basename(path)}".strip(" —")
        self.player_bar.set_track(track)
        self.player.play_file(path)

    def _ensure_video_window(self):
        if self._video_window is None:
            self._video_window = VideoWindow(self.player, self)
            self._video_window.closed.connect(self.player.stop)
        return self._video_window

    # ================================================== файлы и папки
    def reveal_media(self, media_id):
        row = self.db.media(media_id)
        if row and row["file_path"]:
            self.reveal_path(row["file_path"])

    def reveal_path(self, path):
        try:
            os.startfile(os.path.dirname(os.path.abspath(path)))  # noqa: S606
        except OSError as e:
            self.statusBar().showMessage(f"Не удалось открыть папку: {e}", 6000)

    def delete_download(self, media_id):
        row = self.db.media(media_id)
        if not row or not row["file_path"]:
            return
        name = os.path.basename(row["file_path"])
        ans = QMessageBox.question(
            self, "Удаление файла",
            f"Удалить с диска файл?\n{name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            if os.path.exists(row["file_path"]):
                os.remove(row["file_path"])
        except OSError as e:
            QMessageBox.warning(self, "Удаление файла", f"Не удалось удалить:\n{e}")
        self.db.set_media_downloaded(media_id, None)
        if self.stack.currentIndex() == 1:
            self.reload_downloads()
        if self._current_article_id and row["article_id"] == self._current_article_id:
            article = self.db.article(self._current_article_id)
            if article:
                media = self.db.media_for_article(self._current_article_id)
                self.details.show_article(article, media)
        self.statusBar().showMessage(f"Удалено: {name}", 5000)

    def open_downloads_folder(self):
        try:
            os.makedirs(str(self.dl_dir), exist_ok=True)
            os.startfile(str(self.dl_dir))  # noqa: S606
        except OSError as e:
            self.statusBar().showMessage(f"Не удалось открыть папку: {e}", 6000)

    def choose_downloads_folder(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Папка для загрузок", str(self.dl_dir)
        )
        if directory:
            self.dl_dir = Path(directory)
            self.db.set_setting("download_dir", directory)
            self.statusBar().showMessage(f"Папка загрузок: {directory}", 5000)

    # ======================================================= прочее
    def _show_about(self):
        QMessageBox.about(
            self, "О программе",
            f"<b>{APP_NAME} {__version__}</b><br>"
            "Читалка RSS-лент со скачиванием и локальным воспроизведением "
            "аудио и видео.<br>Python + PySide6 (Qt). Лицензия MIT.",
        )

    def closeEvent(self, event):
        self.manager.shutdown()
        self.player.stop()
        if self._refresh_worker is not None:
            try:
                if self._refresh_worker.isRunning():
                    self._refresh_worker.wait(4000)
            except RuntimeError:
                pass
        if self._video_window is not None:
            self._video_window.close()
        super().closeEvent(event)
