package com.rssreader.app.rss

import com.rssreader.app.data.AppDatabase
import com.rssreader.app.data.Article
import com.rssreader.app.data.Feed
import com.rssreader.app.data.Media
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.concurrent.TimeUnit

class FeedSyncer(private val db: AppDatabase) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .followRedirects(true)
        .build()

    /** Обновить все ленты. Возвращает (успешно, с ошибками). */
    suspend fun syncAll(): Pair<Int, Int> = withContext(Dispatchers.IO) {
        var ok = 0
        var failed = 0
        for (feed in db.feedDao().list()) {
            try {
                sync(feed)
                ok++
            } catch (e: Exception) {
                failed++
            }
        }
        ok to failed
    }

    suspend fun sync(feed: Feed): Int = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(feed.url)
            .header("User-Agent", "Mozilla/5.0 (Linux; Android 15) RSSReader/1.0")
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("HTTP ${response.code}")
            val body = response.body ?: throw IOException("пустой ответ")
            val parsed = RssParser.parse(body.byteStream())

            db.feedDao().touched(
                feed.id,
                parsed.title.ifBlank { feed.url },
                System.currentTimeMillis(),
            )

            var fresh = 0
            for (item in parsed.items) {
                val existing = db.articleDao().byGuid(feed.id, item.guid)
                val articleId = if (existing == null) {
                    fresh++
                    db.articleDao().insert(
                        Article(
                            feedId = feed.id,
                            guid = item.guid,
                            title = item.title,
                            link = item.link,
                            published = item.published,
                            summary = item.summary,
                        )
                    )
                } else {
                    db.articleDao().update(
                        existing.copy(
                            title = item.title,
                            link = item.link ?: existing.link,
                            published = item.published ?: existing.published,
                            summary = item.summary,
                        )
                    )
                    existing.id
                }
                for (m in item.media) {
                    db.mediaDao().insert(
                        Media(articleId = articleId, url = m.url, mime = m.mime, size = m.size)
                    )
                }
            }
            fresh
        }
    }
}
