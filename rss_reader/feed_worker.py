"""Фоновое обновление RSS-лент (отдельный поток)."""
import time

import feedparser
import requests
from PySide6.QtCore import QThread, Signal

from .db import Database
from .utils import classify_media

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RSSReader/1.0"


def _as_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _media_candidates(entry):
    """Собрать все возможные медиа-ссылки записи (enclosure, media:content, ссылка)."""
    out = []
    for enc in entry.get("enclosures", []) or []:
        out.append((enc.get("href"), enc.get("type"), enc.get("length")))
    for link in entry.get("links", []) or []:
        if link.get("rel") == "enclosure":
            out.append((link.get("href"), link.get("type"), link.get("length")))
    for mc in entry.get("media_content", []) or []:
        out.append((mc.get("url"), mc.get("type"), mc.get("filesize") or mc.get("fileSize")))
    if entry.get("link"):
        out.append((entry.get("link"), None, None))
    return out


def refresh_feed(db: Database, feed) -> int:
    """Загрузить и разобрать одну ленту. Возвращает число новых статей."""
    resp = requests.get(feed["url"], headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    if not parsed.entries and getattr(parsed, "bozo", 0):
        raise RuntimeError(f"не удалось разобрать ленту ({parsed.bozo_exception})")

    title = (parsed.feed.get("title") or feed["url"]).strip()
    db.update_feed_meta(feed["id"], title, parsed.feed.get("link"))

    known = {r["guid"] for r in db.article_guids(feed["id"])}
    fresh = 0
    for entry in parsed.entries[:100]:
        guid = entry.get("id") or entry.get("link") or entry.get("title")
        if not guid:
            continue
        tm = entry.get("published_parsed") or entry.get("updated_parsed")
        published = time.strftime("%Y-%m-%dT%H:%M:%S", tm) if tm else None
        article_id, is_new = db.upsert_article(
            feed["id"],
            guid,
            entry.get("title") or "(без заголовка)",
            entry.get("link"),
            published,
            entry.get("summary") or entry.get("description") or "",
        )
        if guid not in known:
            fresh += 1
        for url, mime, size in _media_candidates(entry):
            kind = classify_media(url, mime)
            if kind:
                db.add_media(article_id, url, mime, _as_int(size), kind)
    return fresh


class RefreshWorker(QThread):
    """Последовательно обновляет список лент, сигнализирует о прогрессе."""

    feed_done = Signal(int, int)   # feed_id, число новых статей
    feed_error = Signal(str, str)  # название ленты, текст ошибки
    all_done = Signal()

    def __init__(self, db_path: str, feeds, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._feeds = feeds

    def run(self):
        db = Database(self._db_path)
        for feed in self._feeds:
            try:
                fresh = refresh_feed(db, feed)
                self.feed_done.emit(feed["id"], fresh)
            except Exception as e:  # noqa: BLE001
                self.feed_error.emit(
                    feed.get("title") or feed["url"], str(e) or type(e).__name__
                )
        self.all_done.emit()
