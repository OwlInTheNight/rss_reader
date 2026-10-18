package com.rssreader.app.playback

import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.MediaItem
import androidx.media3.session.MediaController
import java.io.File

/** Точка доступа UI к MediaController сервису воспроизведения. */
object PlaybackConnection {
    var controller: MediaController? by mutableStateOf(null)

    fun playFile(path: String) {
        val c = controller ?: return
        c.setMediaItem(MediaItem.fromUri(Uri.fromFile(File(path))))
        c.prepare()
        c.play()
    }
}
