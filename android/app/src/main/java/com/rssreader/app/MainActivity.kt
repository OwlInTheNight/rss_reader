package com.rssreader.app

import android.app.DownloadManager
import android.content.ComponentName
import android.content.IntentFilter
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.content.ContextCompat
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.rssreader.app.downloads.DownloadCompleteReceiver
import com.rssreader.app.playback.PlaybackConnection
import com.rssreader.app.playback.PlaybackService
import com.rssreader.app.ui.App
import com.rssreader.app.ui.theme.RssTheme
import com.google.common.util.concurrent.ListenableFuture

class MainActivity : ComponentActivity() {

    private var controllerFuture: ListenableFuture<MediaController>? = null
    private var downloadReceiver: DownloadCompleteReceiver? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val app = application as RssApp
        downloadReceiver = DownloadCompleteReceiver(app.container.downloads).also { receiver ->
            ContextCompat.registerReceiver(
                this,
                receiver,
                IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE),
                ContextCompat.RECEIVER_NOT_EXPORTED,
            )
        }

        setContent {
            RssTheme {
                App()
            }
        }
    }

    override fun onStart() {
        super.onStart()
        if (controllerFuture == null) {
            val token = SessionToken(this, ComponentName(this, PlaybackService::class.java))
            val future = MediaController.Builder(this, token).buildAsync()
            future.addListener(
                { PlaybackConnection.controller = runCatching { future.get() }.getOrNull() },
                ContextCompat.getMainExecutor(this),
            )
            controllerFuture = future
        }
    }

    override fun onStop() {
        super.onStop()
        controllerFuture?.let { MediaController.releaseFuture(it) }
        controllerFuture = null
        PlaybackConnection.controller = null
    }

    override fun onDestroy() {
        downloadReceiver?.let { runCatching { unregisterReceiver(it) } }
        downloadReceiver = null
        super.onDestroy()
    }
}
