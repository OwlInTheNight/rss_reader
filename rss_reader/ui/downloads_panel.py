"""Панель «Загрузки»: активные задачи и скачанные файлы."""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QLabel, QProgressBar, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..utils import format_size

ROLE = Qt.ItemDataRole.UserRole


class DownloadsPanel(QWidget):
    play_requested = Signal(int)
    reveal_requested = Signal(int)
    delete_requested = Signal(int)
    cancel_requested = Signal(int)
    open_folder_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = {}  # media_id -> отображаемое имя

        v = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel("Загрузки")
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        hint = QLabel("аудио и видео из ваших лент")
        hint.setStyleSheet("color: #888;")
        btn_folder = QPushButton("📁 Открыть папку")
        btn_folder.clicked.connect(self.open_folder_requested.emit)
        head.addWidget(title)
        head.addWidget(hint)
        head.addStretch(1)
        head.addWidget(btn_folder)
        v.addLayout(head)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Название", "Состояние", "Прогресс", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(44)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 180)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 122)
        v.addWidget(self.table)

    # ---------------------------------------------------- публичное API
    def reload_items(self, rows) -> None:
        """Полностью перестроить список (rows — скачанные медиа из БД)."""
        ids = {r["id"] for r in rows}
        self.table.setRowCount(0)
        for r in rows:
            self._append_downloaded(r)
        for mid, name in list(self._active.items()):
            if mid not in ids:
                self._append_active(mid, name, "В очереди")

    def add_active(self, media_id: int, name: str) -> None:
        self._active[media_id] = name
        if self._row_of(media_id) < 0:
            self._append_active(media_id, name, "В очереди")

    def update_progress(self, media_id: int, pct: int, status: str) -> None:
        row = self._row_of(media_id)
        if row < 0:
            self.add_active(media_id, self._active.get(media_id, "Загрузка"))
            row = self._row_of(media_id)
            if row < 0:
                return
        self.table.item(row, 1).setText(str(status))
        bar = self.table.cellWidget(row, 2)
        if isinstance(bar, QProgressBar):
            if pct < 0:
                bar.setRange(0, 0)
            else:
                bar.setRange(0, 100)
                bar.setValue(int(pct))

    def finish_active(self, media_id: int) -> None:
        self._active.pop(media_id, None)
        self._remove_row(media_id)

    def fail_active(self, media_id: int) -> None:
        self._active.pop(media_id, None)
        self._remove_row(media_id)

    # -------------------------------------------------------- внутреннее
    def _append_downloaded(self, r: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        name = os.path.basename(r["file_path"])
        it = QTableWidgetItem(name)
        it.setToolTip(r["file_path"])
        it.setData(ROLE, r["id"])
        self.table.setItem(row, 0, it)
        try:
            size = format_size(os.path.getsize(r["file_path"]))
        except OSError:
            size = ""
        status = QTableWidgetItem("✓ скачано" + (f" · {size}" if size else ""))
        self.table.setItem(row, 1, status)
        done = QLabel("Готово")
        done.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 2, done)
        self.table.setCellWidget(row, 3, self._buttons_widget(r["id"], active=False))

    def _append_active(self, media_id: int, name: str, status: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        it = QTableWidgetItem(name or "Загрузка")
        it.setData(ROLE, media_id)
        self.table.setItem(row, 0, it)
        self.table.setItem(row, 1, QTableWidgetItem(status))
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(14)
        self.table.setCellWidget(row, 2, bar)
        self.table.setCellWidget(row, 3, self._buttons_widget(media_id, active=True))

    def _buttons_widget(self, media_id: int, active: bool) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(2, 2, 2, 2)
        h.setSpacing(4)

        def btn(text, tip, signal):
            b = QPushButton(text)
            b.setFixedSize(36, 28)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, mid=media_id: signal.emit(mid))
            return b

        if active:
            h.addWidget(btn("✖", "Отменить загрузку", self.cancel_requested))
        else:
            h.addWidget(btn("▶", "Воспроизвести", self.play_requested))
            h.addWidget(btn("📁", "Показать в папке", self.reveal_requested))
            h.addWidget(btn("🗑", "Удалить файл", self.delete_requested))
        return w

    def _row_of(self, media_id: int) -> int:
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.data(ROLE) == media_id:
                return r
        return -1

    def _remove_row(self, media_id: int) -> None:
        row = self._row_of(media_id)
        if row >= 0:
            self.table.removeRow(row)
