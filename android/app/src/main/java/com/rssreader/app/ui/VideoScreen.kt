package com.rssreader.app.ui

import android.app.Activity
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.media3.ui.PlayerView
import androidx.navigation.NavHostController
import com.rssreader.app.data.Media
import com.rssreader.app.playback.PlaybackConnection
import com.rssreader.app.vm.AppViewModel

@Composable
fun VideoScreen(vm: AppViewModel, nav: NavHostController, id: Long) {
    val media by produceState<Media?>(null, id) { value = vm.mediaById(id) }

    BackHandler {
        PlaybackConnection.controller?.pause()
        nav.popBackStack()
    }

    // полноэкранный режим: спрятать системные панели
    val view = LocalView.current
    DisposableEffect(Unit) {
        val window = (view.context as Activity).window
        val controller = WindowCompat.getInsetsController(window, window.decorView)
        controller.hide(WindowInsetsCompat.Type.systemBars())
        onDispose { controller.show(WindowInsetsCompat.Type.systemBars()) }
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        val path = media?.filePath
        if (path == null) {
            CircularProgressIndicator(
                Modifier.align(Alignment.Center),
                color = Color.White,
            )
        } else {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        useController = true
                        setShutterBackgroundColor(android.graphics.Color.BLACK)
                    }
                },
                update = { playerView ->
                    playerView.player = PlaybackConnection.controller
                },
            )
            androidx.compose.runtime.LaunchedEffect(path) {
                PlaybackConnection.playFile(path)
            }
        }
    }
}
