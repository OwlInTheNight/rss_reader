package com.rssreader.app.ui

import android.os.Build
import android.text.Html
import java.io.File
import java.text.DateFormat
import java.util.Date

private val AUDIO_EXTS = setOf(
    "mp3", "m4a", "m4b", "aac", "ogg", "oga", "opus", "wav", "flac", "wma", "weba",
)
private val VIDEO_EXTS = setOf(
    "mp4", "m4v", "webm", "mkv", "mov", "avi", "mpg", "mpeg", "flv", "ts", "ogv", "3gp", "wmv",
)

private val MIME_TO_EXT = mapOf(
    "audio/mpeg" to "mp3", "audio/mp3" to "mp3", "audio/mp4" to "m4a",
    "audio/x-m4a" to "m4a", "audio/aac" to "aac", "audio/ogg" to "ogg",
    "audio/opus" to "opus", "audio/wav" to "wav", "audio/x-wav" to "wav",
    "audio/flac" to "flac", "video/mp4" to "mp4", "video/webm" to "webm",
    "video/x-matroska" to "mkv", "video/quicktime" to "mov",
    "video/x-msvideo" to "avi", "video/mpeg" to "mpg",
)

fun extFromUrl(url: String): String? =
    url.substringBefore('?').substringAfterLast('.', "").lowercase().ifEmpty { null }
        ?.takeIf { it in AUDIO_EXTS || it in VIDEO_EXTS }

fun extFromMime(mime: String?): String? =
    mime?.split(';')?.first()?.trim()?.lowercase()?.let { MIME_TO_EXT[it] }

fun isVideo(path: String): Boolean =
    path.substringBefore('?').substringAfterLast('.', "").lowercase() in VIDEO_EXTS

fun sanitizeName(name: String): String {
    val cleaned = name.trim()
        .replace(Regex("""[<>:"/\\|?*\u0000-\u001f]"""), "_")
        .replace(Regex("\\s+"), " ")
        .trim(' ', '.')
    return cleaned.take(100).ifEmpty { "file" }
}

fun formatSize(bytes: Long?): String {
    if (bytes == null || bytes <= 0) return ""
    var n = bytes.toDouble()
    for (unit in listOf("Б", "КБ", "МБ", "ГБ", "ТБ")) {
        if (n < 1024 || unit == "ТБ") {
            return if (unit == "Б") "${n.toInt()} $unit" else "%.1f $unit".format(n)
        }
        n /= 1024.0
    }
    return "%.1f ТБ".format(n)
}

fun formatDate(millis: Long?): String {
    if (millis == null) return ""
    return DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT)
        .format(Date(millis))
}

/** HTML из RSS-описания → читаемый текст. */
fun htmlToText(html: String): String {
    val spanned = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
        Html.fromHtml(html, Html.FROM_HTML_MODE_LEGACY)
    } else {
        @Suppress("DEPRECATION")
        Html.fromHtml(html)
    }
    return spanned.toString()
        .replace(Regex("\n{3,}"), "\n\n")
        .trim()
}

fun fileNameOf(path: String): String = File(path).name
