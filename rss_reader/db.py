"""Локальное хранилище на SQLite: ленты, статьи, медиа, настройки.

Соединение открывается на каждый вызов, поэтому класс безопасно
использовать из нескольких потоков (обновление лент, загрузки, UI).
"""
import os
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    site_url TEXT,
    added_at TEXT DEFAULT (datetime('now','localtime')),
    last_fetched TEXT
);

CREATE TABLE IF NOT EXISTS articles(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    guid TEXT NOT NULL,
    title TEXT,
    link TEXT,
    published TEXT,
    summary TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    UNIQUE(feed_id, guid)
);

CREATE TABLE IF NOT EXISTS media(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    mime TEXT,
    size INTEGER,
    kind TEXT NOT NULL DEFAULT 'file',
    file_path TEXT,
    downloaded_at TEXT,
    UNIQUE(article_id, url)
);

CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_feed ON articles(feed_id, published);
CREATE INDEX IF NOT EXISTS idx_media_article ON media(article_id);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------- ленты
    def add_feed(self, url: str, title=None):
        """Добавить ленту. None — если такая уже есть."""
        with self._conn() as c:
            try:
                cur = c.execute("INSERT INTO feeds(url, title) VALUES(?, ?)", (url.strip(), title))
                return cur.lastrowid
            except sqlite3.IntegrityError:
                return None

    def delete_feed(self, feed_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))

    def list_feeds(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM feeds ORDER BY LOWER(COALESCE(title, url))"
            ).fetchall()
        return [dict(r) for r in rows]

    def feed(self, feed_id: int):
        with self._conn() as c:
            r = c.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        return dict(r) if r else None

    def update_feed_meta(self, feed_id: int, title: str, site_url=None) -> None:
        with self._conn() as c:
            c.execute(
                """UPDATE feeds
                   SET title = ?, site_url = COALESCE(?, site_url),
                       last_fetched = datetime('now','localtime')
                   WHERE id = ?""",
                (title, site_url, feed_id),
            )

    def feed_counts(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT feed_id, COUNT(*) AS n FROM articles GROUP BY feed_id"
            ).fetchall()
        return {r["feed_id"]: r["n"] for r in rows}

    # ----------------------------------------------------------- статьи
    def upsert_article(self, feed_id, guid, title, link, published, summary):
        """Вставить статью или обновить её. Возвращает (id, is_new)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT id FROM articles WHERE feed_id = ? AND guid = ?", (feed_id, guid)
            ).fetchone()
            if row is None:
                cur = c.execute(
                    "INSERT INTO articles(feed_id, guid, title, link, published, summary)"
                    " VALUES(?, ?, ?, ?, ?, ?)",
                    (feed_id, guid, title, link, published, summary),
                )
                return cur.lastrowid, True
            c.execute(
                """UPDATE articles
                   SET title = COALESCE(?, title), link = COALESCE(?, link),
                       published = COALESCE(?, published), summary = COALESCE(?, summary)
                   WHERE id = ?""",
                (title, link, published, summary, row["id"]),
            )
            return row["id"], False

    def article_guids(self, feed_id: int):
        with self._conn() as c:
            rows = c.execute("SELECT guid FROM articles WHERE feed_id = ?", (feed_id,)).fetchall()
        return [dict(r) for r in rows]

    def articles(self, feed_id=None, limit: int = 1000):
        sql = ("SELECT a.*, f.title AS feed_title FROM articles a"
               " JOIN feeds f ON a.feed_id = f.id")
        params = []
        if feed_id is not None:
            sql += " WHERE a.feed_id = ?"
            params.append(feed_id)
        sql += " ORDER BY COALESCE(a.published, '') DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def article(self, article_id: int):
        with self._conn() as c:
            r = c.execute(
                "SELECT a.*, f.title AS feed_title FROM articles a"
                " JOIN feeds f ON a.feed_id = f.id WHERE a.id = ?",
                (article_id,),
            ).fetchone()
        return dict(r) if r else None

    def set_read(self, article_id: int, read: bool = True) -> None:
        with self._conn() as c:
            c.execute("UPDATE articles SET is_read = ? WHERE id = ?", (1 if read else 0, article_id))

    # ------------------------------------------------------------- медиа
    def add_media(self, article_id, url, mime, size, kind) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO media(article_id, url, mime, size, kind) VALUES(?, ?, ?, ?, ?)",
                (article_id, url, mime, size, kind),
            )

    def media_for_article(self, article_id: int):
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM media WHERE article_id = ? ORDER BY id", (article_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def media(self, media_id: int):
        with self._conn() as c:
            r = c.execute(
                """SELECT m.*, a.title AS article_title, a.feed_id, f.title AS feed_title
                   FROM media m
                   JOIN articles a ON m.article_id = a.id
                   JOIN feeds f ON a.feed_id = f.id
                   WHERE m.id = ?""",
                (media_id,),
            ).fetchone()
        return dict(r) if r else None

    def downloaded_media(self):
        with self._conn() as c:
            rows = c.execute(
                """SELECT m.*, a.title AS article_title, a.feed_id, f.title AS feed_title
                   FROM media m
                   JOIN articles a ON m.article_id = a.id
                   JOIN feeds f ON a.feed_id = f.id
                   WHERE m.file_path IS NOT NULL
                   ORDER BY m.downloaded_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def set_media_downloaded(self, media_id: int, path) -> None:
        with self._conn() as c:
            if path:
                c.execute(
                    "UPDATE media SET file_path = ?, downloaded_at = datetime('now','localtime')"
                    " WHERE id = ?",
                    (path, media_id),
                )
            else:
                c.execute(
                    "UPDATE media SET file_path = NULL, downloaded_at = NULL WHERE id = ?",
                    (media_id,),
                )

    # -------------------------------------------------------- настройки
    def get_setting(self, key: str, default=None):
        with self._conn() as c:
            r = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
