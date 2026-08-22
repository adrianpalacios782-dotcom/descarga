import base64
import os
import sys
import time

import pytest
from PySide6.QtWidgets import QApplication

from src.application.use_cases.create_download import CreateDownloadUseCase
from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import AudioFormat, DownloadType, FormatOption, VideoQualityOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus
from src.presentation.main_window import MainWindow
from src.presentation.view_models.main_view_model import MainViewModel


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def fake_thumbnail_network(monkeypatch):
    monkeypatch.setattr(
        "src.presentation.components.thumbnail_loader.fetch_thumbnail",
        lambda url: TINY_PNG,
    )


class StubPlatformAdapter:
    """Adaptador falso que responde el análisis al instante sin red."""

    def __init__(self, metadata: MediaMetadata | None = None) -> None:
        self._metadata = metadata or make_metadata()

    def detect(self, url: Url) -> bool:
        return True

    def analyze(self, url: Url) -> MediaMetadata:
        return self._metadata


def make_metadata(**overrides) -> MediaMetadata:
    url = Url("https://www.youtube.com/watch?v=abc12345678")
    options = [
        VideoQualityOption(
            height=1080, label="Mejor calidad", badge="HD", video_format_id="137+140",
            audio_format_id="140", needs_ffmpeg_merge=True,
            estimated_size_bytes=84 * 1024 * 1024, fps=30.0, extension="mp4",
            is_best_quality=True,
        ),
        VideoQualityOption(
            height=720, label="720p", badge="", video_format_id="136+140",
            audio_format_id="140", needs_ffmpeg_merge=True,
            estimated_size_bytes=48 * 1024 * 1024, fps=30.0, extension="mp4",
        ),
    ]
    fields = dict(
        media_id=MediaId.from_string(url.value),
        url=url,
        platform="YouTube",
        title="Video de Prueba Completo",
        author="Canal Oficial",
        description="Sinopsis del contenido de prueba para el flujo completo.",
        duration_seconds=512.0,
        thumbnail_url="https://i.ytimg.com/vi/abc/maxresdefault.jpg",
        upload_date="20240815",
        video_quality_options=options,
        audio_formats=[AudioFormat(format_id="140", extension="m4a", bitrate_kbps=128.0, filesize_bytes=8 * 1024 * 1024)],
    )
    fields.update(overrides)
    return MediaMetadata(**fields)


class TestWindowFactory:

    def build(self, qapp, adapter=None):
        db_mgr = DatabaseManager(":memory:")
        repo = SQLiteDownloadRepository(db_mgr)
        event_bus = InProcessEventBus()
        engine = YtDlpDownloadEngine(event_bus=event_bus, ffmpeg_adapter=FFmpegProcessAdapter())
        vm = MainViewModel(
            platform_adapter=adapter or StubPlatformAdapter(),
            download_engine=engine,
            repository=repo,
            event_bus=event_bus,
        )
        window = MainWindow(view_model=vm)
        return window, repo, db_mgr


def wait_until(condition, timeout_s: float = 5.0, qapp=None) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        QApplication.processEvents()
        if condition():
            return True
        time.sleep(0.05)
    return False


class TestAnalyzePreviewFlowE2E:

    def test_full_flow_analyze_renders_preview_and_thumbnail(self, qapp) -> None:
        window, _, db_mgr = TestWindowFactory().build(qapp)
        inicio = window.inicio_view

        assert inicio.preview_card.isHidden()

        inicio.url_input.setText("https://www.youtube.com/watch?v=abc12345678")
        inicio.btn_analyze.click()

        assert wait_until(lambda: not inicio.preview_card.isHidden(), qapp=qapp), (
            "La tarjeta de previsualización no apareció tras analizar"
        )
        assert inicio.lbl_status.property("state") == "success"
        assert inicio.lbl_title.text() == "Video de Prueba Completo"
        assert inicio.chip_platform.text() == "YouTube"
        assert inicio.chip_year.text() == "Publicado en 2024"
        assert not inicio.thumbnail.isHidden()
        assert wait_until(lambda: inicio.thumbnail._pixmap is not None), "La miniatura asíncrona no cargó"

        rows = list(inicio._iter_quality_rows())
        assert len(rows) == 2
        assert rows[0].radio.isChecked()
        window.close()
        db_mgr.close()


class TestDescargasCardStates:

    def _make_task(self, tmp_path, platform="YouTube", title="Tarea Uno"):
        url = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        media = make_metadata(platform=platform, title=title)
        fmt = FormatOption(format_id="vq_best", extension="mp4")
        return DownloadTask(
            id=DownloadId.generate(),
            media=media,
            selected_format=fmt,
            destination_path=str(tmp_path / "salida.mp4"),
        )

    def test_card_humanized_states_and_completion_actions(self, qapp, tmp_path) -> None:
        window, _, db_mgr = TestWindowFactory().build(qapp)
        task = self._make_task(tmp_path)

        window.descargas_view.add_task(task)
        card = window.descargas_view.cards[task.id.value]

        assert card.status_label.text() == "En cola"

        window.descargas_view.set_state(task.id.value, "PAUSED")
        assert card.status_label.text() == "Pausada"
        assert not card.btn_resume.isHidden()
        assert card.btn_show_file.isHidden()

        window.descargas_view.set_state(task.id.value, "DOWNLOADING")
        assert card.status_label.text() == "Descargando"
        assert card.telemetry_label.text().count("·") == 2

        window.descargas_view.set_state(task.id.value, "COMPLETED")
        assert card.status_label.text() == "Completada"
        assert not card.btn_show_file.isHidden()
        assert not card.btn_open_folder.isHidden()
        window.close()
        db_mgr.close()

    def test_created_task_appears_in_descargas_after_use_case(self, qapp, tmp_path) -> None:
        window, repo, db_mgr = TestWindowFactory().build(qapp)
        create_uc = CreateDownloadUseCase(repo)

        task = create_uc.execute(
            media=make_metadata(),
            format_id="vq_best",
            destination_path=str(tmp_path / "video.mp4"),
        )
        window.view_model.download_created.emit(task)
        window.descargas_view.add_task(task)
        assert task.id.value in window.descargas_view.cards
        window.close()
        db_mgr.close()


class TestHistorialFilters:

    def test_history_load_search_and_platform_filter(self, qapp, tmp_path) -> None:
        window, _, db_mgr = TestWindowFactory().build(qapp)
        view = window.historial_view

        t1_url = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        t1_media = make_metadata(title="Receta de pasta casera")
        t2_url = Url("https://www.tiktok.com/@user/video/99887766")
        t2_media = make_metadata(
            platform="TikTok", title="Baile viral en la playa"
        )
        tasks = []
        for media, url in ((t1_media, t1_url), (t2_media, t2_url)):
            tasks.append(DownloadTask(
                id=DownloadId.generate(),
                media=media,
                selected_format=FormatOption(format_id="vq_best", extension="mp4"),
                destination_path=str(tmp_path / "x.mp4"),
            ))

        view.load_history(tasks)
        assert view.table.rowCount() == 2
        assert view.table.item(0, 6).text() == "En cola"
        assert view.table.item(0, 5).text() != "-"

        view.search_input.setText("baile")
        assert view.table.rowCount() == 1
        assert view.table.item(0, 0).text() == "Baile viral en la playa"

        view.search_input.setText("")
        view.combo_platform.setCurrentText("YouTube")
        assert view.table.rowCount() == 1
        assert view.table.item(0, 1).text() == "YouTube"

        view.combo_platform.setCurrentText("Todas las plataformas")
        assert view.table.rowCount() == 2
        window.close()
        db_mgr.close()


class TestWiringIntegrity:

    def test_descargas_open_actions_routed_to_window_handlers(self, qapp, monkeypatch) -> None:
        calls = []

        monkeypatch.setattr(
            "src.presentation.main_window.MainWindow._open_in_explorer",
            staticmethod(lambda path: calls.append(("file", path))),
        )
        monkeypatch.setattr(
            "src.presentation.main_window.MainWindow._open_folder",
            staticmethod(lambda path: calls.append(("folder", path))),
        )

        window, _, db_mgr = TestWindowFactory().build(qapp)
        window.descargas_view.open_file_requested.emit(r"C:\descargas\video.mp4")
        window.descargas_view.open_folder_requested.emit(r"C:\descargas\video.mp4")

        assert ("file", r"C:\descargas\video.mp4") in calls
        assert ("folder", r"C:\descargas\video.mp4") in calls
        window.close()
        db_mgr.close()
