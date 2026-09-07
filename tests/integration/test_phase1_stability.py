"""Pruebas de integración para las mejoras de estabilidad y seguridad de la Fase 1."""
import os
import threading
import pytest

from src.domain.entities.download_task import DownloadTask
from src.domain.entities.favorite_item import FavoriteItem
from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_favorite_repository import SQLiteFavoriteRepository
from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository
from src.infrastructure.adapters.storage.sqlite_settings_repository import SQLiteSettingsRepository


class TestPhase1Stability:
    """Verifica protecciones de seguridad, plantillas outtmpl y persistencia multihilo."""

    def test_unc_network_path_rejected_by_security(self) -> None:
        with pytest.raises(RuntimeError, match="Rutas de red UNC no permitidas"):
            YtDlpDownloadEngine._validate_destination_path("\\\\attacker-ip\\share\\video.mp4")

        with pytest.raises(RuntimeError, match="Rutas de red UNC no permitidas"):
            YtDlpDownloadEngine._validate_destination_path("//attacker-ip/share/video.mp4")

    def test_destination_path_escaping_percent_symbol(self) -> None:
        raw_base = "Video 100% Real (Full HD)"
        safe_base = raw_base.replace("%", "%%")
        assert safe_base == "Video 100%% Real (Full HD)"

        # Simulando el formateo interno de yt-dlp outtmpl con formato dict
        outtmpl = os.path.join("C:/downloads", safe_base + ".%(ext)s")
        formatted = outtmpl % {"ext": "mp4"}
        assert "100% Real" in formatted
        assert formatted.endswith(".mp4")

    def test_sqlite_repositories_share_central_rlock(self) -> None:
        db = DatabaseManager(":memory:")
        dl_repo = SQLiteDownloadRepository(db)
        fav_repo = SQLiteFavoriteRepository(db)
        set_repo = SQLiteSettingsRepository(db)

        # Todos los repositorios deben compartir exactamente la misma instancia del lock
        assert dl_repo._lock is db.lock
        assert fav_repo._lock is db.lock
        assert set_repo._lock is db.lock

    def test_sqlite_concurrent_multithread_access(self) -> None:
        db = DatabaseManager(":memory:")
        dl_repo = SQLiteDownloadRepository(db)
        fav_repo = SQLiteFavoriteRepository(db)
        set_repo = SQLiteSettingsRepository(db)

        errors = []

        def worker_downloads():
            try:
                for i in range(20):
                    url = Url(f"https://youtube.com/watch?v=vid{i}")
                    media = MediaMetadata(media_id=MediaId.generate(), url=url, platform="YouTube", title=f"Video {i}")
                    fmt = FormatOption(format_id="137", extension="mp4", height=1080)
                    task = DownloadTask(id=DownloadId.generate(), media=media, selected_format=fmt, destination_path=f"C:/downloads/{i}.mp4")
                    dl_repo.save(task)
            except Exception as e:
                errors.append(e)

        def worker_favorites():
            try:
                for i in range(20):
                    fav = FavoriteItem(
                        url=f"https://youtube.com/watch?v=fav{i}",
                        title=f"Fav {i}",
                        author="Channel",
                        platform="YouTube",
                    )
                    fav_repo.add(fav)
            except Exception as e:
                errors.append(e)

        def worker_settings():
            try:
                for i in range(20):
                    set_repo.set(f"key_{i}", f"value_{i}")
                    _ = set_repo.get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker_downloads),
            threading.Thread(target=worker_favorites),
            threading.Thread(target=worker_settings),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Ocurrieron errores de concurrencia: {errors}"
