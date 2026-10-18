package com.rssreader.app

import android.app.Application
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.rssreader.app.data.AppDatabase
import com.rssreader.app.downloads.DownloadQueue
import com.rssreader.app.rss.FeedSyncer
import com.rssreader.app.work.SyncWorker
import java.util.concurrent.TimeUnit

class RssApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)

        val request = PeriodicWorkRequestBuilder<SyncWorker>(30, TimeUnit.MINUTES).build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "rss-sync", ExistingPeriodicWorkPolicy.KEEP, request
        )
    }
}

class AppContainer(context: android.content.Context) {
    val db: AppDatabase = AppDatabase.build(context)
    val syncer = FeedSyncer(db)
    val downloads = DownloadQueue(context.applicationContext, db)
}
