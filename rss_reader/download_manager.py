"""Очередь загрузок медиафайлов в фоновом потоке.

Поддерживает два типа задач:
- "file" — прямая ссылка на аудио/видео, качается через requests;
- "link" — страница видео (YouTube и т.п.), качается через yt-dlp.
"""
import os
import queue
import shutil
import threading
from dataclasses import dataclass, field

import requests
from PySide6.QtCore import QObject, Signal

from .utils import ffmpeg_available, format_size, unique_path

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RSSReader/1.0"}


class DownloadCancelled(Exception):
    """Загрузка отменена пользователем."""


@dataclass
class DownloadTask:
    media_id: int
    url: str
    kind: str          # "file" | "link"
    dest_dir: str
    name: str = ""     # для "file" — итоговое имя файла
    audio_only: bool = False
    cancelled: threading.Event = field(default_factory=threading.Event)
    tmp_path: str | None = None


def _as_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


class DownloadManager(QObject):
    progress = Signal(int, int, str)  # media_id, процент (-1 — неизвестен), статус
    finished = Signal(int, str)       # media_id, путь к файлу
    failed = Signal(int, str)         # media_id, текст ошибки

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: queue.Queue = queue.Queue()
        self._tasks: dict[int, DownloadTask] = {}
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ----------------------------------------------------------- публичное
    def enqueue(self, task: DownloadTask) -> None:
        with self._lock:
            self._tasks[task.media_id] = task
        self._queue.put(task)

    def cancel(self, media_id: int) -> None:
        with self._lock:
            task = self._tasks.get(media_id)
        if task:
            task.cancelled.set()

    def shutdown(self) -> None:
        with self._lock:
            for task in self._tasks.values():
                task.cancelled.set()
        self._queue.put(None)
        self._thread.join(timeout=2)

    # --------------------------------------------------------- поток
    def _run(self):
        while True:
            task = self._queue.get()
            if task is None:
                break
            try:
                if task.cancelled.is_set():
                    raise DownloadCancelled()
                path = (self._download_file(task) if task.kind == "file"
                        else self._download_link(task))
                if task.cancelled.is_set():
                    raise DownloadCancelled()
                self.finished.emit(task.media_id, path)
            except DownloadCancelled:
                self._cleanup(task)
                self.failed.emit(task.media_id, "Отменено")
            except Exception as e:  # noqa: BLE001
                self._cleanup(task)
                self.failed.emit(task.media_id, str(e) or type(e).__name__)
            finally:
                with self._lock:
                    self._tasks.pop(task.media_id, None)

    @staticmethod
    def _cleanup(task: DownloadTask) -> None:
        if task.tmp_path:
            try:
                if os.path.exists(task.tmp_path):
                    os.remove(task.tmp_path)
            except OSError:
                pass

    # -------------------------------------------------- прямая ссылка
    def _download_file(self, t: DownloadTask) -> str:
        os.makedirs(t.dest_dir, exist_ok=True)
        base, ext = os.path.splitext(t.name or "file")
        path = unique_path(os.path.join(t.dest_dir, (base or "file") + (ext or ".bin")))
        t.tmp_path = path
        self.progress.emit(t.media_id, 0, "Подключение…")
        with requests.get(t.url, headers=HEADERS, stream=True, timeout=(10, 60)) as r:
            r.raise_for_status()
            total = _as_int(r.headers.get("Content-Length")) or 0
            done = 0
            last_pct = -1
            with open(path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=65536):
                    if t.cancelled.is_set():
                        raise DownloadCancelled()
                    if not chunk:
                        continue
                    fh.write(chunk)
                    done += len(chunk)
                    pct = int(done * 100 / total) if total else -1
                    if pct != last_pct:
                        last_pct = pct
                        text = format_size(done)
                        if total:
                            text += f" / {format_size(total)}"
                        self.progress.emit(t.media_id, pct, text)
        t.tmp_path = None
        return path

    # -------------------------------------------------- страница видео (yt-dlp)
    def _download_link(self, t: DownloadTask) -> str:
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("yt-dlp не установлен (pip install yt-dlp)")

        os.makedirs(t.dest_dir, exist_ok=True)
        has_ffmpeg = shutil and ffmpeg_available()

        def hook(d):
            if t.cancelled.is_set():
                raise DownloadCancelled()
            status = d.get("status")
            if status == "downloading":
                done = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = int(done * 100 / total) if total else -1
                text = f"Скачивание… {format_size(done)}"
                if total:
                    text += f" / {format_size(total)}"
                self.progress.emit(t.media_id, pct, text)
            elif status == "finished":
                self.progress.emit(t.media_id, -1, "Обработка…")

        opts = {
            "outtmpl": os.path.join(t.dest_dir, "%(title).150B.%(ext)s"),
            "progress_hooks": [hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "windowsfilenames": True,
            "retries": 3,
        }
        if t.audio_only:
            opts["format"] = "bestaudio/best"
            if has_ffmpeg:
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
        elif has_ffmpeg:
            opts["format"] = "bv*+ba/b"
            opts["merge_output_format"] = "mp4"
        else:
            # без ffmpeg берём одиночный файл, который не требует склейки
            opts["format"] = "best[ext=mp4]/best"

        self.progress.emit(t.media_id, -1, "Получение информации…")
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(t.url, download=True)
            path = None
            for item in (info or {}).get("requested_downloads") or []:
                if item.get("filepath"):
                    path = item["filepath"]
            if (not path or not os.path.exists(path)) and info:
                try:
                    path = ydl.prepare_filename(info)
                except Exception:
                    path = None
            if not path or not os.path.exists(path):
                raise RuntimeError("не удалось определить имя скачанного файла")
            if t.cancelled.is_set():
                raise DownloadCancelled()
            return path
