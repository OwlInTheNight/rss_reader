package com.rssreader.app.vm

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.rssreader.app.RssApp
import com.rssreader.app.data.Article
import com.rssreader.app.data.Feed
import com.rssreader.app.data.Media
import com.rssreader.app.data.MediaRow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File

data class ArticleContext(
    val article: Article,
    val feedTitle: String,
    val media: List<Media>,
)

class AppViewModel(app: Application) : AndroidViewModel(app) {
    private val container = (app as RssApp).container
    private val db = container.db

    val feeds: StateFlow<List<Feed>> = db.feedDao().all()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val counts: StateFlow<Map<Long, Int>> = db.articleDao().counts()
        .map { list -> list.associate { it.feedId to it.n } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyMap())

    val downloaded: StateFlow<List<MediaRow>> = db.mediaDao().downloaded()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val active: StateFlow<List<MediaRow>> = db.mediaDao().active()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    var refreshing by mutableStateOf(false)
        private set
    var message by mutableStateOf<String?>(null)

    fun articlesFlow(feedId: Long?) = db.articleDao().articles(feedId)

    suspend fun articleFull(id: Long): ArticleContext? {
        val article = db.articleDao().get(id) ?: return null
        val feedTitle = db.feedDao().get(article.feedId)?.title.orEmpty()
        return ArticleContext(article, feedTitle, db.mediaDao().forArticle(id))
    }

    suspend fun mediaById(id: Long): Media? = db.mediaDao().get(id)

    fun refresh() {
        viewModelScope.launch {
            refreshing = true
            val (ok, failed) = container.syncer.syncAll()
            refreshing = false
            message = when {
                ok > 0 && failed == 0 -> "Обновлено лент: $ok"
                ok > 0 -> "Обновлено: $ok, с ошибками: $failed"
                else -> "Не удалось обновить ленты"
            }
        }
    }

    fun addFeed(urlRaw: String) {
        val url = urlRaw.trim()
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            message = "Нужен URL, начинающийся с http:// или https://"
            return
        }
        viewModelScope.launch {
            val existing = db.feedDao().byUrl(url)
            if (existing != null) {
                message = "Такая лента уже есть"
                return@launch
            }
            val id = db.feedDao().insert(Feed(url = url, title = url))
            val feed = db.feedDao().get(id) ?: return@launch
            message = "Добавлено, обновляем…"
            runCatching { container.syncer.sync(feed) }
                .onSuccess { message = "Лента добавлена" }
                .onFailure { message = "Не удалось загрузить ленту" }
        }
    }

    fun deleteFeed(id: Long) {
        viewModelScope.launch { db.feedDao().delete(id) }
    }

    fun markRead(id: Long) {
        viewModelScope.launch { db.articleDao().markRead(id) }
    }

    fun startDownload(media: Media, articleTitle: String, feedTitle: String) {
        container.downloads.enqueue(media, articleTitle, feedTitle)
        message = "Загрузка начата: $articleTitle"
    }

    fun cancelDownload(row: MediaRow) {
        viewModelScope.launch {
            db.mediaDao().get(row.id)?.let { container.downloads.cancel(it) }
        }
    }

    fun deleteDownload(row: MediaRow) {
        viewModelScope.launch {
            row.filePath?.let { runCatching { File(it).delete() } }
            db.mediaDao().setDownloaded(row.id, null, null)
        }
    }

    fun progressFor(row: MediaRow): Pair<Int, String>? =
        row.downloadId?.let { container.downloads.progressFor(it) }
}
