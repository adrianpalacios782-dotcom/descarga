import os
import sys
import pytest
from PySide6.QtWidgets import QApplication

from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus
from src.presentation.main_window import MainWindow
from src.presentation.view_models.main_view_model import MainViewModel


# Asegurar instancia de QApplication para pruebas de interfaz de usuario
@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class TestGuiE2E:

    def test_main_window_tabs_and_navigation(self, qapp) -> None:
        db_mgr = DatabaseManager(":memory:")
        repo = SQLiteDownloadRepository(db_mgr)
        event_bus = InProcessEventBus()
        registry = PlatformRegistry()
        engine = YtDlpDownloadEngine(event_bus=event_bus, ffmpeg_adapter=FFmpegProcessAdapter())

        vm = MainViewModel(
            platform_adapter=registry,
            download_engine=engine,
            repository=repo,
            event_bus=event_bus
        )

        window = MainWindow(view_model=vm)
        window.show()

        # Probar navegación por las 6 vistas
        for idx in range(6):
            window.sidebar.button_group.button(idx).click()
            assert window.stacked.currentIndex() == idx

        window.close()
        db_mgr.close()

    def test_audio_bitrate_options_per_format(self, qapp) -> None:
        """Los bitrates ofrecidos dependen del formato de audio (honestos y producibles)."""
        db_mgr = DatabaseManager(":memory:")
        repo = SQLiteDownloadRepository(db_mgr)
        event_bus = InProcessEventBus()
        registry = PlatformRegistry()
        engine = YtDlpDownloadEngine(event_bus=event_bus, ffmpeg_adapter=FFmpegProcessAdapter())

        vm = MainViewModel(
            platform_adapter=registry,
            download_engine=engine,
            repository=repo,
            event_bus=event_bus
        )

        window = MainWindow(view_model=vm)
        inicio = window.stacked.widget(0)
        combo_fmt = inicio.combo_audio_fmt
        combo_br = inicio.combo_audio_br

        def bitrates():
            return [combo_br.itemData(i) for i in range(combo_br.count())]

        # MP3: 320/256/192/128, habilitado
        combo_fmt.setCurrentIndex(combo_fmt.findData("mp3"))
        assert bitrates() == [320, 256, 192, 128]
        assert combo_br.isEnabled()

        # M4A: 192/160/128 (AAC no requiere 320), habilitado
        combo_fmt.setCurrentIndex(combo_fmt.findData("m4a"))
        assert bitrates() == [192, 160, 128]
        assert combo_br.isEnabled()

        # WAV: sin compresión, bitrate deshabilitado
        combo_fmt.setCurrentIndex(combo_fmt.findData("wav"))
        assert not combo_br.isEnabled()
        assert combo_br.currentText() == "Sin compresión"

        window.close()
        db_mgr.close()
