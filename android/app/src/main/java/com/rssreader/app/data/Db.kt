package com.rssreader.app.data

import android.content.Context
import androidx.room.Database
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "feeds")
data class Feed(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val url: String,
    val title: String,
    val lastFetched: Long? = null,
)

@Entity(
    tableName = "articles",
    foreignKeys = [ForeignKey(
        entity = Feed::class, parentColumns = ["id"], childColumns = ["feedId"],
        onDelete = ForeignKey.CASCADE,
    )],
    indices = [Index("feedId"), Index(value = ["feedId", "guid"], unique = true)],
)
data class Article(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val feedId: Long,
    val guid: String,
    val title: String,
    val link: String? = null,
    val published: Long? = null,
    val summary: String = "",
    val isRead: Boolean = false,
)

@Entity(
    tableName = "media",
    foreignKeys = [ForeignKey(
        entity = Article::class, parentColumns = ["id"], childColumns = ["articleId"],
        onDelete = ForeignKey.CASCADE,
    )],
    indices = [Index("articleId"), Index(value = ["articleId", "url"], unique = true)],
)
data class Media(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val articleId: Long,
    val url: String,
    val mime: String? = null,
    val size: Long? = null,
    val kind: String = "file",
    val filePath: String? = null,
    val downloadId: Long? = null,
    val downloadedAt: Long? = null,
)

/** Строка списка статей (статья + название ленты). */
data class ArticleListItem(
    val id: Long,
    val feedId: Long,
    val title: String,
    val link: String?,
    val published: Long?,
    val isRead: Boolean,
    val feedTitle: String,
)

/** Строка списка медиа (вложения/загрузки + контекст). */
data class MediaRow(
    val id: Long,
    val articleId: Long,
    val url: String,
    val mime: String?,
    val size: Long?,
    val filePath: String?,
    val downloadId: Long?,
    val articleTitle: String,
    val feedTitle: String,
)

data class FeedCount(val feedId: Long, val n: Int)

@androidx.room.Dao
interface FeedDao {
    @Query("SELECT * FROM feeds ORDER BY title COLLATE NOCASE")
    fun all(): Flow<List<Feed>>

    @Query("SELECT * FROM feeds")
    suspend fun list(): List<Feed>

    @Query("SELECT * FROM feeds WHERE id = :id")
    suspend fun get(id: Long): Feed?

    @Query("SELECT * FROM feeds WHERE url = :url")
    suspend fun byUrl(url: String): Feed?

    @Insert
    suspend fun insert(feed: Feed): Long

    @Query("UPDATE feeds SET title = :title, lastFetched = :ts WHERE id = :id")
    suspend fun touched(id: Long, title: String, ts: Long)

    @Query("DELETE FROM feeds WHERE id = :id")
    suspend fun delete(id: Long)
}

@androidx.room.Dao
interface ArticleDao {
    @Query(
        """SELECT a.id AS id, a.feedId AS feedId, a.title AS title, a.link AS link,
                  a.published AS published, a.isRead AS isRead, f.title AS feedTitle
           FROM articles a JOIN feeds f ON a.feedId = f.id
           WHERE (:feedId IS NULL OR a.feedId = :feedId)
           ORDER BY COALESCE(a.published, 0) DESC
           LIMIT 500"""
    )
    fun articles(feedId: Long?): Flow<List<ArticleListItem>>

    @Query("SELECT feedId AS feedId, COUNT(*) AS n FROM articles GROUP BY feedId")
    fun counts(): Flow<List<FeedCount>>

    @Query("SELECT * FROM articles WHERE id = :id")
    suspend fun get(id: Long): Article?

    @Query("SELECT * FROM articles WHERE feedId = :feedId AND guid = :guid")
    suspend fun byGuid(feedId: Long, guid: String): Article?

    @Insert
    suspend fun insert(article: Article): Long

    @Update
    suspend fun update(article: Article)

    @Query("UPDATE articles SET isRead = 1 WHERE id = :id")
    suspend fun markRead(id: Long)
}

@androidx.room.Dao
interface MediaDao {
    @Query("SELECT * FROM media WHERE articleId = :articleId ORDER BY id")
    suspend fun forArticle(articleId: Long): List<Media>

    @Query("SELECT * FROM media WHERE id = :id")
    suspend fun get(id: Long): Media?

    @Query(
        """SELECT m.id AS id, m.articleId AS articleId, m.url AS url, m.mime AS mime,
                  m.size AS size, m.filePath AS filePath, m.downloadId AS downloadId,
                  a.title AS articleTitle, f.title AS feedTitle
           FROM media m
           JOIN articles a ON m.articleId = a.id
           JOIN feeds f ON a.feedId = f.id
           WHERE m.filePath IS NOT NULL
           ORDER BY m.id DESC"""
    )
    fun downloaded(): Flow<List<MediaRow>>

    @Query(
        """SELECT m.id AS id, m.articleId AS articleId, m.url AS url, m.mime AS mime,
                  m.size AS size, m.filePath AS filePath, m.downloadId AS downloadId,
                  a.title AS articleTitle, f.title AS feedTitle
           FROM media m
           JOIN articles a ON m.articleId = a.id
           JOIN feeds f ON a.feedId = f.id
           WHERE m.downloadId IS NOT NULL AND m.filePath IS NULL
           ORDER BY m.id DESC"""
    )
    fun active(): Flow<List<MediaRow>>

    @Insert(onConflict = androidx.room.OnConflictStrategy.IGNORE)
    suspend fun insert(media: Media)

    @Query("UPDATE media SET downloadId = :downloadId WHERE id = :id")
    suspend fun setDownloadId(id: Long, downloadId: Long?)

    @Query("UPDATE media SET filePath = :path, downloadedAt = :ts WHERE id = :id")
    suspend fun setDownloaded(id: Long, path: String?, ts: Long?)
}

@Database(
    entities = [Feed::class, Article::class, Media::class],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun feedDao(): FeedDao
    abstract fun articleDao(): ArticleDao
    abstract fun mediaDao(): MediaDao

    companion object {
        fun build(context: android.content.Context): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, "rss_reader.db")
                .fallbackToDestructiveMigration()
                .build()
    }
}
