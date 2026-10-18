package com.rssreader.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.rssreader.app.data.MediaRow
import com.rssreader.app.playback.PlaybackConnection
import com.rssreader.app.vm.AppViewModel
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DownloadsScreen(vm: AppViewModel, nav: NavHostController) {
    val done by vm.downloaded.collectAsStateWithLifecycle()
    val active by vm.active.collectAsStateWithLifecycle()
    var progress by remember { mutableStateOf<Map<Long, Pair<Int, String>>>(emptyMap()) }

    LaunchedEffect(active) {
        while (active.isNotEmpty()) {
            progress = active.mapNotNull { row ->
                val did = row.downloadId ?: return@mapNotNull null
                val p = vm.progressFor(row) ?: return@mapNotNull null
                did to p
            }.toMap()
            delay(1000)
        }
        progress = emptyMap()
    }

    Column(Modifier.fillMaxSize()) {
        TopAppBar(title = { Text("Загрузки") })

        if (active.isEmpty() && done.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    "Здесь появятся скачанные\nаудио и видео из ваших лент",
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            return@Column
        }

        LazyColumn(Modifier.fillMaxSize()) {
            items(active, key = { "active-${it.id}" }) { row ->
                ActiveDownloadRow(row, progress[row.downloadId], vm)
                HorizontalDivider()
            }
            items(done, key = { it.id }) { row ->
                DownloadedRow(row, nav, vm)
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun ActiveDownloadRow(
    row: MediaRow,
    progress: Pair<Int, String>?,
    vm: AppViewModel,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 10.dp)
    ) {
        Text(
            row.articleTitle,
            style = MaterialTheme.typography.titleMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(6.dp))
        val pct = progress?.first ?: -1
        if (pct < 0) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
        } else {
            LinearProgressIndicator(
                progress = { pct / 100f },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        Spacer(Modifier.height(4.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                progress?.second ?: "В очереди",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.weight(1f),
                maxLines = 1,
            )
            TextButton(onClick = { vm.cancelDownload(row) }) { Text("Отмена") }
        }
    }
}

@Composable
private fun DownloadedRow(row: MediaRow, nav: NavHostController, vm: AppViewModel) {
    val path = row.filePath ?: return
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(if (isVideo(path)) "🎬" else "🎧")
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(
                fileNameOf(path),
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                row.feedTitle,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        IconButton(onClick = {
            if (isVideo(path)) {
                nav.navigate("video/${row.id}")
            } else {
                PlaybackConnection.playFile(path)
            }
        }) {
            Icon(Icons.Filled.PlayArrow, "Воспроизвести")
        }
        IconButton(onClick = { vm.deleteDownload(row) }) {
            Icon(
                Icons.Filled.Delete,
                "Удалить",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
