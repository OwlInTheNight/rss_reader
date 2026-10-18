# 📰 RSS Reader — читалка RSS с загрузкой и воспроизведением медиа

Десктопное приложение для **Windows**: читайте RSS/Atom-ленты, скачивайте аудио- и видеофайлы из статей и воспроизводите их прямо в программе.

## Возможности

- ➕ Подписка на RSS/Atom-ленты, обновление по F5 (и автоматически при запуске)
- 📖 Список статей с непрочитанными, просмотр описания, переход к оригиналу в браузере
- 🎧 Обнаружение медиа-вложений в статьях (podcast-enclosures, `media:content`)
- ⬇️ Очередь скачивания с прогрессом; файлы раскладываются по папкам лент
- ▶️ Встроенный плеер: аудио — в нижней панели, видео — в отдельном окне (перемотка, громкость)
- 🎬 Поддержка YouTube/Vimeo/Rutube-ссылок из лент через yt-dlp: видео (mp4) или только звук (mp3/m4a)
- 🗂 Настраиваемая папка загрузок, удаление файлов из программы
- 💾 Все данные локальны: SQLite-база в `%APPDATA%\RSSReader`

## Требования

- Windows 10/11
- Python 3.10+ (тестировалось на 3.14)
- Зависимости из `requirements.txt` (PySide6, feedparser, requests, yt-dlp)
- *Необязательно:* [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) в `PATH` — для склейки YouTube-видео в mp4 и конвертации звука в mp3. Без ffmpeg видео скачивается одним файлом, звук — в m4a.

## Быстрый старт

```bat
git clone https://github.com/USERNAME/rss_reader.git
cd rss_reader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Вместо venv можно установить зависимости глобально: `pip install -r requirements.txt`.

## Использование

1. **Добавьте ленту**: кнопка `➕` или `Ленты → Добавить ленту` (Ctrl+N). Примеры:
   - `https://feeds.arstechnica.com/arstechnica/index` — новости
   - `https://hnrss.org/frontpage` — Hacker News
   - `https://lexfridman.com/feed/podcast/` — подкаст (mp3)
   - YouTube-канал: `https://www.youtube.com/feeds/videos.xml?channel_id=<ID канала>`
2. **Читайте**: слева ленты, в центре список статей, внизу — описание и вложения.
3. **Скачивайте**: у вложения нажмите `⬇ Скачать` (или `⬇ Видео` / `⬇ Аудио` для YouTube).
4. **Смотрите/слушайте**: кнопка `▶` в статье или на панели «⬇ Загрузки».

### Где хранятся данные

| Что | Где |
|---|---|
| База данных | `%APPDATA%\RSSReader\rss_reader.db` |
| Загрузки | `Downloads\RSSReader\<название ленты>\` (настраивается) |

## Структура проекта

```
rss_reader/
├── main.py                  # точка входа
├── requirements.txt
└── rss_reader/
    ├── db.py                # SQLite-хранилище (ленты, статьи, медиа, настройки)
    ├── feed_worker.py       # фоновое обновление лент
    ├── download_manager.py  # очередь загрузок (requests + yt-dlp)
    ├── player.py            # обёртка QMediaPlayer
    ├── utils.py             # утилиты
    └── ui/                  # интерфейс (PySide6)
        ├── main_window.py   # главное окно
        ├── details.py       # просмотр статьи + вложения
        ├── downloads_panel.py
        ├── player_bar.py
        └── video_window.py
```

## Публикация на GitHub

Репозиторий уже инициализирован и содержит первый коммит. Чтобы залить на GitHub:

1. Создайте пустой репозиторий на [github.com/new](https://github.com/new) (без README и .gitignore).
2. Выполните в папке проекта:

```bash
git remote add origin https://github.com/USERNAME/rss_reader.git
git branch -M main
git push -u origin main
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
