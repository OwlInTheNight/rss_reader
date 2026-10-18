package com.rssreader.app.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.rssreader.app.RssApp

/** Периодическое обновление лент (WorkManager, каждые 30 минут). */
class SyncWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val container = (applicationContext as RssApp).container
        return try {
            container.syncer.syncAll()
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }
}
