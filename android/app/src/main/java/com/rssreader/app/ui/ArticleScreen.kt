package com.rssreader.app.ui

import android.content.Intent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.rssreader.app.data.Media
import com.rssreader.app.playback.PlaybackConnection
import com.rssreader.app.vm.AppViewModel
import androidx.compose.ui.text.style.TextAlign

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ArticleScreen(vm: AppViewModel, nav: NavHostController, id: Long) {
    val context = LocalContext.current
    val full by produceState<com.rssreader.app.vm.ArticleContext?>(null, id) {
        value = vm.articleFull(id)
    }

    Column(Modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text("Статья", maxLines = 1, overflow = TextOverflow.Ellipsis) },
            navigationIcon = {
                IconButton(onClick = { nav.popBackStack() }) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад")
                }
            },
        )

        val data = full
        if (data == null) {
            Column(
                Modifier.fillMaxSize(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center,
            ) {
                CircularProgressIndicator()
                Spacer(Modifier.height(12.dp))
                Text("Загрузка…", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            return@Column
        }

        val article = data.article
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            Text(
                article.title,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(6.dp))
            val meta = listOfNotNull(
                data.feedTitle.ifEmpty { null },
                formatDate(article.published).ifEmpty { null },
            ).joinToString(" · ")
            Text(
                meta,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))

            val text = htmlToText(article.summary)
            if (text.isNotEmpty()) {
                Text(
                    text,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.9f),
                )
                Spacer(Modifier.height(12.dp))
            }

            article.link?.let { link ->
                TextButton(onClick = {
                    runCatching {
                        context.startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(link)))
                    }
                }) { Text("🔗 Открыть оригинал в браузере") }
                Spacer(Modifier.height(8.dp))
            }

            if (data.media.isNotEmpty()) {
                Text(
                    "Вложения (${data.media.size})",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(4.dp))
                data.media.forEach { media ->
                    MediaItemRow(
                        media = media,
                        articleTitle = article.title,
                        feedTitle = data.feedTitle,
                        vm = vm,
                        nav = nav,
                    )
                }
            } else {
                Text(
                    "В этой статье нет медиа-вложений",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Start,
                )
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun MediaItemRow(
    media: Media,
    articleTitle: String,
    feedTitle: String,
    vm: AppViewModel,
    nav: NavHostController,
) {
    val path = media.filePath
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(if (isVideo(path ?: media.url)) "🎬" else "🎧")
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(
                fileNameOf(path ?: media.url),
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            val size = formatSize(media.size)
            if (size.isNotEmpty()) {
                Text(
                    size,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.width(8.dp))
        if (path != null) {
            Button(onClick = {
                if (isVideo(path)) {
                    nav.navigate("video/${media.id}")
                } else {
                    PlaybackConnection.playFile(path)
                }
            }) {
                Text(if (isVideo(path)) "Смотреть" else "Слушать")
            }
        } else {
            Button(onClick = { vm.startDownload(media, articleTitle, feedTitle) }) {
                Text("⬇ Скачать")
            }
        }
    }
}
