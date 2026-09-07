import pytest
from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository


class TestSQLiteDownloadRepository:

    @pytest.fixture
    def db_repo(self):
        db_mgr = DatabaseManager(":memory:")
        repo = SQLiteDownloadRepository(db_mgr)
        yield repo
        db_mgr.close()

    @pytest.fixture
    def sample_task(self) -> DownloadTask:
        url = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        media_id = MediaId.from_string(url.value)
        fmt = FormatOption(
            format_id="1080p_mp4",
            extension="mp4",
            resolution="1080p",
            width=1920,
            height=1080,
            fps=60.0,
            filesize_bytes=150 * 1024 * 1024
        )
        media = MediaMetadata(
            media_id=media_id,
            url=url,
            platform="YouTube",
            title="Video Demostración SQLite",
            author="Canal Pruebas",
            duration_seconds=240.0,
            formats=[fmt]
        )
        return DownloadTask(
            id=DownloadId.generate(),
            media=media,
            selected_format=fmt,
            destination_path="C:/Downloads/video.mp4"
        )

    def test_save_and_get_by_id(self, db_repo: SQLiteDownloadRepository, sample_task: DownloadTask) -> None:
        db_repo.save(sample_task)

        retrieved = db_repo.get_by_id(sample_task.id)
        assert retrieved is not None
        assert retrieved.id == sample_task.id
        assert retrieved.media.title == "Video Demostración SQLite"
        assert retrieved.media.platform == "YouTube"
        assert retrieved.selected_format.format_id == "1080p_mp4"
        assert retrieved.status == DownloadState.QUEUED

    def test_update_task_state_and_progress(self, db_repo: SQLiteDownloadRepository, sample_task: DownloadTask) -> None:
        db_repo.save(sample_task)

        # Transicionar y actualizar progreso
        sample_task.transition_to(DownloadState.DOWNLOADING)
        sample_task.update_progress(downloaded_bytes=5000, total_bytes=10000, speed_bps=1024.0, eta_seconds=5.0)
        db_repo.save(sample_task)

        updated = db_repo.get_by_id(sample_task.id)
        assert updated is not None
        assert updated.status == DownloadState.DOWNLOADING
        assert updated.downloaded_bytes == 5000
        assert updated.progress_percent == 50.0
        assert updated.speed_bps == 1024.0

    def test_get_all_and_delete(self, db_repo: SQLiteDownloadRepository, sample_task: DownloadTask) -> None:
        db_repo.save(sample_task)

        all_tasks = db_repo.get_all()
        assert len(all_tasks) == 1
        assert all_tasks[0].id == sample_task.id

        db_repo.delete(sample_task.id)
        assert db_repo.get_by_id(sample_task.id) is None
        assert len(db_repo.get_all()) == 0

    def test_quality_warning_roundtrip(self, db_repo: SQLiteDownloadRepository, sample_task: DownloadTask) -> None:
        """Una tarea completada con advertencia de calidad degradada persiste y recupera el aviso."""
        sample_task.transition_to(DownloadState.DOWNLOADING)
        sample_task.quality_warning = (
            "Calidad degradada: se solicitó 1080p pero el archivo resultante "
            "tiene 806p@24fps. La resolución solicitada no pudo ser entregada."
        )
        sample_task.complete()
        db_repo.save(sample_task)

        retrieved = db_repo.get_by_id(sample_task.id)
        assert retrieved is not None
        assert retrieved.status == DownloadState.COMPLETED
        assert retrieved.error_message is None
        assert "806p@24fps" in (retrieved.quality_warning or "")
        assert "1080p" in (retrieved.quality_warning or "")

    def test_v120_metadata_roundtrip(self, db_repo: SQLiteDownloadRepository, sample_task: DownloadTask) -> None:
        """Verifica que time_range, audio_preset y embed_thumbnail persistan y se recuperen fielmente."""
        from src.domain.value_objects.time_range import TimeRange
        from src.domain.value_objects.audio_preset import AudioPreset

        sample_task.time_range = TimeRange(start_seconds=15.0, end_seconds=75.0)
        sample_task.audio_preset = AudioPreset.MP3_320K
        sample_task.embed_thumbnail = True
        db_repo.save(sample_task)

        retrieved = db_repo.get_by_id(sample_task.id)
        assert retrieved is not None
        assert retrieved.time_range is not None
        assert retrieved.time_range.start_seconds == 15.0
        assert retrieved.time_range.end_seconds == 75.0
        assert retrieved.audio_preset == AudioPreset.MP3_320K
        assert retrieved.embed_thumbnail is True

    def test_migration_from_legacy_schema(self) -> None:
        """Simula una base de datos antigua (sin columnas de v1.2.0) y valida la migración transparente."""
        db_mgr = DatabaseManager(":memory:")
        conn = db_mgr.get_connection()
        # Crear schema base como en v1.0.0
        conn.executescript("""
            CREATE TABLE media_items (
                id TEXT PRIMARY KEY,
                original_url TEXT NOT NULL,
                platform_name TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT,
                duration_seconds REAL DEFAULT 0,
                thumbnail_url TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE format_options (
                id TEXT PRIMARY KEY,
                media_id TEXT NOT NULL,
                format_id TEXT NOT NULL,
                extension TEXT NOT NULL,
                resolution TEXT,
                width INTEGER,
                height INTEGER,
                fps REAL,
                filesize_bytes INTEGER,
                is_audio_only INTEGER DEFAULT 0,
                is_video_only INTEGER DEFAULT 0
            );
            CREATE TABLE download_tasks (
                id TEXT PRIMARY KEY,
                media_id TEXT NOT NULL,
                chosen_format_id TEXT NOT NULL,
                destination_path TEXT NOT NULL,
                current_state TEXT NOT NULL,
                progress_percent REAL DEFAULT 0.0,
                downloaded_bytes INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0,
                speed_bps REAL DEFAULT 0.0,
                eta_seconds REAL DEFAULT 0.0,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            );
        """)
        # Inicializar repositorio, disparando la migración
        repo = SQLiteDownloadRepository(db_mgr)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(download_tasks)").fetchall()]
        assert "time_range_start" in cols
        assert "time_range_end" in cols
        assert "audio_preset" in cols
        assert "embed_thumbnail" in cols
        db_mgr.close()
