import sqlite3
import threading
from datetime import datetime
from typing import Any, List, Optional

from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption, StreamType, DownloadType
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.ports.download_repository import IDownloadRepository
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager


class SQLiteDownloadRepository(IDownloadRepository):
    """Implementación concreta del repositorio de descargas utilizando SQLite (thread-safe)."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self._lock = threading.RLock()
        self.db_manager.init_tables()

    def save(self, task: DownloadTask) -> None:
        with self._lock:
            conn = self.db_manager.get_connection()
            media = task.media
            fmt = task.selected_format

            with conn:
                # 1. Guardar/Actualizar media_item
                conn.execute(
                    """
                    INSERT INTO media_items (id, original_url, platform_name, title, author, duration_seconds, thumbnail_url, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        author=excluded.author,
                        duration_seconds=excluded.duration_seconds,
                        thumbnail_url=excluded.thumbnail_url
                    """,
                    (
                        media.media_id.value,
                        media.url.value,
                        media.platform,
                        media.title,
                        media.author,
                        media.duration_seconds,
                        media.thumbnail_url,
                        datetime.now().isoformat()
                    )
                )

                # 2. Guardar format_option con metadata completa
                fmt_pk = f"{media.media_id.value}_{fmt.format_id}"
                conn.execute(
                    """
                    INSERT INTO format_options (
                        id, media_id, format_id, extension, resolution, width, height, fps, filesize_bytes,
                        is_audio_only, is_video_only, stream_type, needs_ffmpeg_merge, audio_format_id,
                        bitrate_kbps, target_audio_format, target_audio_bitrate, is_best_quality,
                        video_codec, audio_codec
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        extension=excluded.extension,
                        resolution=excluded.resolution,
                        width=excluded.width,
                        height=excluded.height,
                        fps=excluded.fps,
                        filesize_bytes=excluded.filesize_bytes,
                        is_audio_only=excluded.is_audio_only,
                        is_video_only=excluded.is_video_only,
                        stream_type=excluded.stream_type,
                        needs_ffmpeg_merge=excluded.needs_ffmpeg_merge,
                        audio_format_id=excluded.audio_format_id,
                        bitrate_kbps=excluded.bitrate_kbps,
                        target_audio_format=excluded.target_audio_format,
                        target_audio_bitrate=excluded.target_audio_bitrate,
                        is_best_quality=excluded.is_best_quality,
                        video_codec=excluded.video_codec,
                        audio_codec=excluded.audio_codec
                    """,
                    (
                        fmt_pk,
                        media.media_id.value,
                        fmt.format_id,
                        fmt.extension,
                        fmt.resolution,
                        fmt.width,
                        fmt.height,
                        fmt.fps,
                        fmt.filesize_bytes,
                        1 if fmt.is_audio_only else 0,
                        1 if fmt.is_video_only else 0,
                        fmt.stream_type.value,
                        1 if fmt.needs_ffmpeg_merge else 0,
                        fmt.audio_format_id,
                        fmt.bitrate_kbps,
                        fmt.target_audio_format,
                        fmt.target_audio_bitrate,
                        1 if fmt.is_best_quality else 0,
                        fmt.video_codec,
                        fmt.audio_codec
                    )
                )

                # 3. Guardar/Actualizar download_task
                conn.execute(
                    """
                    INSERT INTO download_tasks (
                        id, media_id, chosen_format_id, destination_path, current_state,
                        progress_percent, downloaded_bytes, total_bytes, speed_bps, eta_seconds,
                        error_message, quality_warning, created_at, started_at, completed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        current_state=excluded.current_state,
                        progress_percent=excluded.progress_percent,
                        downloaded_bytes=excluded.downloaded_bytes,
                        total_bytes=excluded.total_bytes,
                        speed_bps=excluded.speed_bps,
                        eta_seconds=excluded.eta_seconds,
                        error_message=excluded.error_message,
                        quality_warning=excluded.quality_warning,
                        started_at=excluded.started_at,
                        completed_at=excluded.completed_at
                    """,
                    (
                        task.id.value,
                        media.media_id.value,
                        fmt.format_id,
                        task.destination_path,
                        task.status.value,
                        task.progress_percent,
                        task.downloaded_bytes,
                        task.total_bytes,
                        task.speed_bps,
                        task.eta_seconds,
                        task.error_message,
                        task.quality_warning,
                        task.created_at.isoformat(),
                        task.started_at.isoformat() if task.started_at else None,
                        task.completed_at.isoformat() if task.completed_at else None
                    )
                )

    def get_by_id(self, task_id: DownloadId) -> Optional[DownloadTask]:
        with self._lock:
            return self._query_single("WHERE dt.id = ?", (task_id.value,))

    def get_all(self) -> List[DownloadTask]:
        with self._lock:
            conn = self.db_manager.get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT dt.*, mi.original_url, mi.platform_name, mi.title, mi.author, mi.duration_seconds, mi.thumbnail_url,
                       fo.format_id, fo.extension, fo.resolution, fo.width, fo.height, fo.fps, fo.filesize_bytes,
                       fo.is_audio_only, fo.is_video_only, fo.stream_type, fo.needs_ffmpeg_merge, fo.audio_format_id,
                       fo.bitrate_kbps, fo.target_audio_format, fo.target_audio_bitrate, fo.is_best_quality,
                       fo.video_codec, fo.audio_codec
                FROM download_tasks dt
                JOIN media_items mi ON dt.media_id = mi.id
                JOIN format_options fo ON (fo.media_id = mi.id AND fo.format_id = dt.chosen_format_id)
                ORDER BY dt.created_at DESC
                """
            )
            rows = cur.fetchall()
            return [self._row_to_task(r) for r in rows]

    def delete(self, task_id: DownloadId) -> None:
        with self._lock:
            conn = self.db_manager.get_connection()
            with conn:
                conn.execute("DELETE FROM download_tasks WHERE id = ?", (task_id.value,))

    def _query_single(self, where_clause: str, params: tuple[Any, ...]) -> Optional[DownloadTask]:
        conn = self.db_manager.get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT dt.*, mi.original_url, mi.platform_name, mi.title, mi.author, mi.duration_seconds, mi.thumbnail_url,
                   fo.format_id, fo.extension, fo.resolution, fo.width, fo.height, fo.fps, fo.filesize_bytes,
                   fo.is_audio_only, fo.is_video_only, fo.stream_type, fo.needs_ffmpeg_merge, fo.audio_format_id,
                   fo.bitrate_kbps, fo.target_audio_format, fo.target_audio_bitrate, fo.is_best_quality,
                   fo.video_codec, fo.audio_codec
            FROM download_tasks dt
            JOIN media_items mi ON dt.media_id = mi.id
            JOIN format_options fo ON (fo.media_id = mi.id AND fo.format_id = dt.chosen_format_id)
            {where_clause}
            """,
            params
        )
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> DownloadTask:
        url = Url(row["original_url"])
        media_id = MediaId(row["media_id"])

        try:
            stream_type = StreamType(row["stream_type"]) if row["stream_type"] else StreamType.VIDEO_AUDIO
        except ValueError:
            stream_type = StreamType.VIDEO_AUDIO

        fmt = FormatOption(
            format_id=row["format_id"],
            extension=row["extension"],
            resolution=row["resolution"] or "",
            width=row["width"],
            height=row["height"],
            fps=row["fps"],
            video_codec=row["video_codec"],
            audio_codec=row["audio_codec"],
            stream_type=stream_type,
            download_type=DownloadType.AUDIO if bool(row["is_audio_only"]) else DownloadType.VIDEO,
            is_audio_only=bool(row["is_audio_only"]),
            is_video_only=bool(row["is_video_only"]),
            is_best_quality=bool(row["is_best_quality"]),
            needs_ffmpeg_merge=bool(row["needs_ffmpeg_merge"]),
            audio_format_id=row["audio_format_id"],
            filesize_bytes=row["filesize_bytes"],
            bitrate_kbps=row["bitrate_kbps"],
            target_audio_format=row["target_audio_format"],
            target_audio_bitrate=row["target_audio_bitrate"]
        )

        media = MediaMetadata(
            media_id=media_id,
            url=url,
            platform=row["platform_name"],
            title=row["title"],
            author=row["author"] or "",
            duration_seconds=row["duration_seconds"] or 0.0,
            thumbnail_url=row["thumbnail_url"] or "",
            formats=[fmt]
        )

        task = DownloadTask(
            id=DownloadId(row["id"]),
            media=media,
            selected_format=fmt,
            destination_path=row["destination_path"],
            status=DownloadState(row["current_state"]),
            progress_percent=row["progress_percent"],
            downloaded_bytes=row["downloaded_bytes"],
            total_bytes=row["total_bytes"],
            speed_bps=row["speed_bps"],
            eta_seconds=row["eta_seconds"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            error_message=row["error_message"],
            quality_warning=row["quality_warning"] if "quality_warning" in row.keys() else None
        )

        return task
