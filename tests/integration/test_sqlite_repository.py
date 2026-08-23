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
