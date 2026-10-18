"""Общие утилиты: пути, имена файлов, определение типов медиа."""
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

APP_DIR_NAME = "RSSReader"

AUDIO_EXTS = {
    "mp3", "m4a", "m4b", "aac", "ogg", "oga", "opus", "wav", "flac", "wma", "weba",
}
VIDEO_EXTS = {
    "mp4", "m4v", "webm", "mkv", "mov", "avi", "mpg", "mpeg", "flv", "ts", "ogv", "3gp", "wmv",
}
MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS

MIME_TO_EXT = {
    "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
    "audio/aac": "aac", "audio/aacp": "aac", "audio/ogg": "ogg", "audio/opus": "opus",
    "audio/wav": "wav", "audio/x-wav": "wav", "audio/flac": "flac", "video/mp4": "mp4",
    "video/webm": "webm", "video/x-matroska": "mkv", "video/quicktime": "mov",
    "video/x-msvideo": "avi", "video/mpeg": "mpg", "video/ogg": "ogv",
    "application/ogg": "ogg",
}

# Сайты, видео с которых скачивает yt-dlp
LINK_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "rutube.ru", "dzen.ru")

DEFAULT_FEEDS = [
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://hnrss.org/frontpage",
    "https://lexfridman.com/feed/podcast/",
]


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    return root / APP_DIR_NAME


def default_db_path() -> str:
    return str(app_data_dir() / "rss_reader.db")


def default_downloads_dir() -> str:
    return str(Path.home() / "Downloads" / APP_DIR_NAME)


def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Привести строку к безопасному для Windows имени файла."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (name or "").strip())
    name = re.sub(r"\s+", " ", name).strip(" .")
    if len(name) > max_len:
        cut = name[:max_len]
        name = cut.rsplit(" ", 1)[0] if " " in cut else cut
        name = name.strip(" .")
    return name or "file"


def ext_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
    except Exception:
        return ""
    return os.path.splitext(path)[1].lstrip(".").lower()


def ext_from_mime(mime) -> str:
    if not mime:
        return ""
    return MIME_TO_EXT.get(str(mime).split(";")[0].strip().lower(), "")


def classify_media(url: str, mime=None):
    """'file' — прямая ссылка на медиафайл, 'link' — страница видео (yt-dlp), None — не медиа."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    m = (mime or "").split(";")[0].strip().lower()
    if m.startswith(("audio/", "video/")):
        return "file"
    if ext_from_url(url) in MEDIA_EXTS:
        return "file"
    host = (urlparse(url).netloc or "").lower()
    if any(h in host for h in LINK_HOSTS):
        return "link"
    return None


def is_video_path(path: str) -> bool:
    return os.path.splitext(path or "")[1].lower().lstrip(".") in VIDEO_EXTS


def format_size(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return "0 Б"
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if n < 1024 or unit == "ТБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} ТБ"


def format_dt(iso) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return str(iso)


def unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def yt_dlp_available() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except Exception:
        return False


def seed_default_feeds(db) -> None:
    """При первом запуске добавить несколько популярных лент."""
    if not db.list_feeds():
        for url in DEFAULT_FEEDS:
            db.add_feed(url)
