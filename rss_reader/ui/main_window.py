"""Главное окно приложения."""
import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QActionGroup, QBrush, QColor,
                           QDesktopServices, QFont)
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu,
                               QMessageBox, QSplitter, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..db import Database
from ..download_manager import DownloadManager, DownloadTask
from ..feed_worker import RefreshWorker
from ..opml import export_opml, import_opml
from ..player import Player
from ..theme import build_qss, detect_system_dark, theme_colors
from ..utils import (default_db_path, default_downloads_dir, ext_from_mime,
                     ext_from_url, format_dt, is_video_path, sanitize_filename,
                     seed_default_feeds)
from .article_delegate import ArticleDelegate, DATA_ROLE
from .details import ArticleDetails
from .downloads_panel import DownloadsPanel
from .player_bar import PlayerBar
from .video_window import VideoWindow

ROLE = Qt.ItemDataRole.UserRole

AUTO_REFRESH_OPTIONS = [
    (0, "Выключено"),
    (5, "Каждые 5 минут"),
    (15, "Каждые 15 минут"),
    (30, "Каждые 30 минут"),
    (60, "Каждый час"),
    (180, "Каждые 3 часа"),
]
DEFAULT_AUTO_REFRESH = 30


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — RSS-читалка с медиа")
        self.resize(1240, 800)
        self.setMinimumSize(980, 620)

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

        self.apply_theme(
            self.db.get_setting("theme") or
            ("dark" if detect_system_dark() else "light")
        )

        self.rebuild_feed_list()
        if self.feed_list.currentRow() < 0:
            self.feed_list.setCurrentRow(0)

        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(lambda: self.refresh_all(auto=True))
        try:
            minutes = int(self.db.get_setting("auto_refresh_min") or DEFAULT_AUTO_REFRESH)
        except ValueError:
            minutes = DEFAULT_AUTO_REFRESH
        if minutes not in dict(AUTO_REFRESH_OPTIONS):
            minutes = DEFAULT_AUTO_REFRESH
        self._auto_actions[minutes].setChecked(True)
        self.set_auto_refresh(minutes)

        if not os.environ.get("RSSREADER_NO_REFRESH"):
            QTimer.singleShot(200, self.refresh_all)

    # ================================================================ UI
    def _build_ui(self):
        self._build_menu()

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(7)

        panel = QWidget()
        panel.setObjectName("panel")
        panel_v = QVBoxLayout(panel)
        panel_v.setContentsMargins(8, 10, 8, 10)
        panel_v.setSpacing(6)

        header = QHBoxLayout()
        cap = QLabel("ЛЕНТЫ")
        cap.setProperty("role", "caption")
        header.addWidget(cap)
        header.addStretch(1)
        btn_add = QToolButton()
        btn_add.setObjectName("iconButton")
        btn_add.setText("＋")
        btn_add.setToolTip("Добавить ленту (Ctrl+N)")
        btn_add.clicked.connect(self.add_feed_dialog)
        btn_ref = QToolButton()
        btn_ref.setObjectName("iconButton")
        btn_ref.setText("⟳")
        btn_ref.setToolTip("Обновить все ленты (F5)")
        btn_ref.clicked.connect(lambda: self.refresh_all())
        header.addWidget(btn_add)
        header.addWidget(btn_ref)
        panel_v.addLayout(header)

        self.feed_list = QListWidget()
        self.feed_list.setObjectName("feedList")
        self.feed_list.setMinimumWidth(220)
        self.feed_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.feed_list.currentItemChanged.connect(self._on_feed_changed)
        self.feed_list.customContextMenuRequested.connect(self._feed_context_menu)
        panel_v.addWidget(self.feed_list)
        splitter.addWidget(panel)

        self.stack = QStackedWidget()
        self.article_list = QListWidget()
        self.article_list.setObjectName("articleList")
        self.article_list.setItemDelegate(ArticleDelegate(self.article_list))
        self.article_list.setMouseTracking(True)
        self.article_list.viewport().setMouseTracking(True)
        self.article_list.setSpacing(2)
        self.article_list.currentItemChanged.connect(self._on_article_changed)
        self.article_list.itemDoubleClicked.connect(self._open_selected_in_browser)
        self.details = ArticleDetails()
        self.art_split = QSplitter(Qt.Orientation.Vertical)
        self.art_split.setChildrenCollapsible(False)
        self.art_split.setHandleWidth(7)
        self.art_split.addWidget(self.article_list)
        self.art_split.addWidget(self.details)
        self.art_split.setSizes([440, 340])
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

        m_auto = QMenu("Автообновление", self)
        group = QActionGroup(self)
        group.setExclusive(True)
        self._auto_actions = {}
        for minutes, label in AUTO_REFRESH_OPTIONS:
            a = QAction(label, self)
            a.setCheckable(True)
            group.addAction(a)
            m_auto.addAction(a)
            a.triggered.connect(lambda _checked=False, m=minutes: self.set_auto_refresh(m))
            self._auto_actions[minutes] = a
        m_feeds.addMenu(m_auto)

        m_feeds.addSeparator()
        a_imp = QAction("Импорт OPML…", self)
        a_imp.triggered.connect(self._import_opml)
        m_feeds.addAction(a_imp)
        a_exp = QAction("Экспорт OPML…", self)
        a_exp.triggered.connect(self._export_opml)
        m_feeds.addAction(a_exp)
        m_feeds.addSeparator()
        a_quit = QAction("Выход", self)
        a_quit.triggered.connect(self.close)
        m_feeds.addAction(a_quit)

        m_view = self.menuBar().addMenu("&Вид")
        self.action_dark = QAction("🌙 Тёмная тема", self)
        self.action_dark.setCheckable(True)
        self.action_dark.setShortcut("Ctrl+T")
        self.action_dark.toggled.connect(
            lambda on: self.apply_theme("dark" if on else "light")
        )
        m_view.addAction(self.action_dark)

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

    # ============================================================= темы
    def apply_theme(self, name: str) -> None:
        self.theme_name = name
        self.db.set_setting("theme", name)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(theme_colors(name)))
        delegate = self.article_list.itemDelegate()
        if isinstance(delegate, ArticleDelegate):
            delegate.set_colors(theme_colors(name))
        self.action_dark.setChecked(name == "dark")

    # ==================================================== автообновление
    def set_auto_refresh(self, minutes: int) -> None:
        self.db.set_setting("auto_refresh_min", str(minutes))
        if minutes > 0:
            self._auto_timer.setInterval(minutes * 60 * 1000)
            self._auto_timer.start()
            label = dict(AUTO_REFRESH_OPTIONS).get(minutes, f"{minutes} мин")
            self.statusBar().showMessage(f"Автообновление: {label.lower()}", 5000)
        else:
            self._auto_timer.stop()
            self.statusBar().showMessage("Автообновление выключено", 5000)

    # ========================================================== OPML
    def _import_opml(self):
        start = os.path.join(str(Path.home()), "Downloads")
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт OPML", start, "OPML (*.opml *.xml);;Все файлы (*)"
        )
        if not path:
            return
        try:
            items = import_opml(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Импорт OPML", f"Не удалось прочитать файл:\n{e}")
            return
        added = skipped = 0
        for url, title in items:
            if self.db.add_feed(url, title) is None:
                skipped += 1
            else:
                added += 1
        self.rebuild_feed_list()
        QMessageBox.information(
            self, "Импорт OPML",
            f"Добавлено лент: {added}\nПропущено (уже есть): {skipped}",
        )
        if added:
            self.refresh_all()

    def _export_opml(self):
        default = os.path.join(str(Path.home()), "Downloads", "rss_reader.opml")
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт OPML", default, "OPML (*.opml)")
        if not path:
            return
        if not path.lower().endswith(".opml"):
            path += ".opml"
        try:
            export_opml(self.db.list_feeds(), path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Экспорт OPML", f"Не удалось записать файл:\n{e}")
            return
        self.statusBar().showMessage(f"Ленты экспортированы: {path}", 6000)

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
            head.setForeground(QBrush(QColor(theme_colors(self.theme_name)["secondary"])))
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

    def refresh_all(self, feeds=None, auto=False):
        if self._refresh_worker is not None:
            try:
                if self._refresh_worker.isRunning():
                    if not auto:
                        self.statusBar().showMessage("Обновление уже выполняется…", 3000)
                    return
            except RuntimeError:
                pass
        feeds = feeds or self.db.list_feeds()
        if not feeds:
            if not auto:
                self.statusBar().showMessage(
                    "Нет лент — добавьте первую через «＋»", 6000
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
            meta = format_dt(r["published"])
            if self.current_feed is None and r["feed_title"]:
                meta = " · ".join(p for p in (meta, r["feed_title"]) if p)
            data = dict(r)
            data["meta_line"] = meta
            it = QListWidgetItem()
            it.setData(DATA_ROLE, data)
            self.article_list.addItem(it)
        self._current_article_id = None
        self.details.clear_article()
        if rows:
            self.statusBar().showMessage(f"Статей: {len(rows)}", 4000)
        else:
            self.details.show_placeholder(
                "Лента пуста", "Обновите ленты (F5) или дождитесь новых публикаций"
            )

    def _on_article_changed(self, current, _previous):
        if current is None:
            return
        data = current.data(DATA_ROLE) or {}
        article_id = data.get("id")
        if not article_id:
            return
        row = self.db.article(article_id)
        if not row:
            return
        self._current_article_id = article_id
        if not row["is_read"]:
            self.db.set_read(article_id)
            data["is_read"] = True
            current.setData(DATA_ROLE, data)
        media = self.db.media_for_article(article_id)
        self.details.show_article(row, media)

    def _open_selected_in_browser(self, item):
        data = item.data(DATA_ROLE) or {}
        row = self.db.article(data.get("id"))
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
