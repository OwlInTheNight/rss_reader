package com.rssreader.app.rss

import android.util.Xml
import org.xmlpull.v1.XmlPullParser
import java.io.InputStream
import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

data class ParsedMedia(val url: String, val mime: String?, val size: Long?)
data class ParsedItem(
    val guid: String,
    val title: String,
    val link: String?,
    val published: Long?,
    val summary: String,
    val media: List<ParsedMedia>,
)

data class ParsedFeed(val title: String, val items: List<ParsedItem>)

private const val AUDIO_EXTS =
    "mp3 m4a m4b aac ogg oga opus wav flac wma weba"
private const val VIDEO_EXTS =
    "mp4 m4v webm mkv mov avi mpg mpeg flv ts ogv 3gp wmv"

/** Разбор RSS 2.0 / Atom с поддержкой enclosure и media:content. */
object RssParser {

    fun parse(input: InputStream): ParsedFeed {
        val parser = Xml.newPullParser().apply {
            setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES, true)
            setInput(input, null)
        }

        var feedTitle = ""
        val items = mutableListOf<ParsedItem>()
        var b: Builder? = null
        val text = StringBuilder()

        var event = parser.eventType
        while (event != XmlPullParser.END_DOCUMENT) {
            val tag = parser.name?.substringAfterLast(':')?.lowercase()
            when (event) {
                XmlPullParser.START_TAG -> when {
                    tag == "item" || tag == "entry" -> b = Builder()

                    b == null && tag == "title" -> Unit // текст соберём в END_TAG

                    b != null -> when (tag) {
                        "link" -> {
                            val href = parser.getAttributeValue(null, "href")
                            val rel = parser.getAttributeValue(null, "rel")
                            if (!href.isNullOrBlank() && (rel == null || rel == "alternate")) {
                                b.link = href
                            }
                        }
                        "enclosure" -> {
                            val url = parser.getAttributeValue(null, "url")
                            if (!url.isNullOrBlank()) {
                                b.media += ParsedMedia(
                                    url,
                                    parser.getAttributeValue(null, "type"),
                                    parser.getAttributeValue(null, "length")?.toLongOrNull(),
                                )
                            }
                        }
                        "content" -> {
                            // media:content (media RSS) — есть атрибут url
                            val url = parser.getAttributeValue(null, "url")
                            if (!url.isNullOrBlank() && isMediaUrl(url)) {
                                b.media += ParsedMedia(
                                    url,
                                    parser.getAttributeValue(null, "type"),
                                    (parser.getAttributeValue(null, "fileSize")
                                        ?: parser.getAttributeValue(null, "filesize"))?.toLongOrNull(),
                                )
                            } else if (b != null) {
                                b.inContent = true
                            }
                        }
                        else -> Unit
                    }

                    else -> Unit
                }

                XmlPullParser.TEXT -> text.append(parser.text)

                XmlPullParser.END_TAG -> {
                    if (tag == "item" || tag == "entry") {
                        b?.let { items += it.build() }
                        b = null
                    } else if (b == null && tag == "title") {
                        if (feedTitle.isBlank()) feedTitle = text.toString().trim()
                    } else if (b != null) when (tag) {
                        "title" -> if (b.title.isBlank()) b.title = text.toString().trim()
                        "link" -> if (b.link.isNullOrBlank()) b.link = text.toString().trim()
                        "guid", "id" -> if (b.guid.isBlank()) b.guid = text.toString().trim()
                        "pubdate", "published", "updated", "date" ->
                            if (b.published == null) b.published = parseDate(text.toString())
                        "description", "summary" ->
                            if (b.summary.isBlank()) b.summary = text.toString().trim()
                        "content" -> if (b.inContent && b.summary.isBlank()) {
                            b.summary = text.toString().trim()
                            b.inContent = false
                        }
                    }
                    text.setLength(0)
                }
            }
            event = parser.next()
        }
        return ParsedFeed(feedTitle, items)
    }

    /** Прямая ли это ссылка на аудио/видео (иначе вложение не показываем). */
    fun isMediaUrl(url: String): Boolean {
        val ext = url.substringBefore('?').substringAfterLast('/').substringAfterLast('.', "")
            .lowercase()
        return ext in AUDIO_EXTS.split(' ') || ext in VIDEO_EXTS.split(' ')
    }

    fun parseDate(raw: String): Long? {
        val s = raw.trim()
        if (s.isEmpty()) return null
        runCatching { return OffsetDateTime.parse(s).toInstant().toEpochMilli() }
        runCatching { return ZonedDateTime.parse(s).toInstant().toEpochMilli() }
        runCatching { return Instant.parse(s).toEpochMilli() }
        runCatching { return LocalDateTime.parse(s).toInstant(ZoneOffset.UTC).toEpochMilli() }
        val formats = listOf(
            "EEE, dd MMM yyyy HH:mm:ss zzz",
            "EEE, dd MMM yyyy HH:mm:ss Z",
            "EEE, dd MMM yyyy HH:mm zzz",
        )
        for (pattern in formats) {
            runCatching {
                val f = DateTimeFormatter.ofPattern(pattern, Locale.US)
                return ZonedDateTime.parse(s, f).toInstant().toEpochMilli()
            }
        }
        return null
    }

    private class Builder {
        var guid = ""
        var title = ""
        var link: String? = null
        var published: Long? = null
        var summary = ""
        var inContent = false
        val media = mutableListOf<ParsedMedia>()

        fun build(): ParsedItem {
            val g = guid.ifBlank { link ?: title }
            return ParsedItem(g, title.ifBlank { "(без заголовка)" }, link, published, summary, media.toList())
        }
    }
}
