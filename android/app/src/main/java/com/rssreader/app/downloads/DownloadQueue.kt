package com.rssreader.app.downloads

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.os.Environment
import com.rssreader.app.data.AppDatabase
import com.rssreader.app.data.Media
import com.rssreader.app.ui.extFromMime
import com.rssreader.app.ui.extFromUrl
import com.rssreader.app.ui.formatSize
import com.rssreader.app.ui.sanitizeName
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Очередь загрузок на системном DownloadManager: прогресс, уведомления, повторы. */
class DownloadQueue(
    context: Context,
    private val db: AppDatabase,
) {
    private val appContext = context.applicationContext
    private val dm = appContext.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
    private val prefs = appContext.getSharedPreferences("downloads", Context.MODE_PRIVATE)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun enqueue(media: Media, articleTitle: String, feedTitle: String): Long {
        val ext = extFromUrl(media.url) ?: extFromMime(media.mime) ?: "bin"
        val relative = "RSSReader/${sanitizeName(feedTitle)}/${sanitizeName(articleTitle)}.$ext"
        val request = DownloadManager.Request(Uri.parse(media.url))
            .setTitle(articleTitle)
            .setDescription(feedTitle)
            .setMimeType(media.mime ?: "*/*")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, relative)
        val downloadId = dm.enqueue(request)
        prefs.edit().putLong("d$downloadId", media.id).apply()
        scope.launch { db.mediaDao().setDownloadId(media.id, downloadId) }
        return downloadId
    }

    /** Прогресс активной загрузки: (процент, текст статуса) или null. */
    fun progressFor(downloadId: Long): Pair<Int, String>? {
        val cursor: Cursor = dm.query(DownloadManager.Query().setFilterById(downloadId))
        cursor.use {
            if (!it.moveToFirst()) return null
            val total = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
            val done =
                it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
            val status = it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
            return when (status) {
                DownloadManager.STATUS_RUNNING -> {
                    val pct = if (total > 0) (done * 100 / total).toInt() else -1
                    val text = if (total > 0) {
                        "Скачивание… ${formatSize(done)} / ${formatSize(total)}"
                    } else {
                        "Скачивание… ${formatSize(done)}"
                    }
                    pct to text
                }
                DownloadManager.STATUS_PENDING -> -1 to "В очереди"
                DownloadManager.STATUS_PAUSED -> -1 to "Пауза"
                DownloadManager.STATUS_SUCCESSFUL -> 100 to "Готово"
                else -> -1 to ""
            }
        }
    }

    fun cancel(media: Media) {
        media.downloadId?.let { id ->
            dm.remove(id)
            prefs.edit().remove("d$id").apply()
        }
        scope.launch { db.mediaDao().setDownloaded(media.id, null, null) }
    }

    fun handleComplete(downloadId: Long) {
        val mediaId = prefs.getLong("d$downloadId", -1L)
        if (mediaId < 0) return
        prefs.edit().remove("d$downloadId").apply()

        val uri = dm.query(DownloadManager.Query().setFilterById(downloadId)).use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(
                cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_LOCAL_URI)
            ) else null
        } ?: return
        val path = Uri.parse(uri).path ?: return
        scope.launch {
            db.mediaDao().setDownloaded(mediaId, path, System.currentTimeMillis())
        }
    }
}

/** Приём «загрузка завершена» от системы. */
class DownloadCompleteReceiver(private val queue: DownloadQueue) : BroadcastReceiver() {
    override fun onReceive(context: Context?, intent: Intent?) {
        val id = intent?.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L) ?: return
        if (id >= 0) queue.handleComplete(id)
    }
}
