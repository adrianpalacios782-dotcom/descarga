"""Pruebas unitarias para Drag & Drop y configuración de fragmentos concurrentes."""

import os
import tempfile
import threading
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication

from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.presentation.views.inicio_view import InicioView
from src.presentation.views.configuracion_view import ConfiguracionView
from src.presentation.view_models.main_view_model import MainViewModel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestConcurrentFragments:

    def test_engine_concurrent_fragments_clamping_and_options(self) -> None:
        engine = YtDlpDownloadEngine(concurrent_fragments=4)
        assert engine.concurrent_fragments == 4

        # Clamping entre 1 y 8
        engine.set_concurrent_fragments(12)
        assert engine.concurrent_fragments == 8

        engine.set_concurrent_fragments(0)
        assert engine.concurrent_fragments == 1

        engine.set_concurrent_fragments(6)
        assert engine.concurrent_fragments == 6

        opts = engine._build_base_opts("out.mp4", "task-1", threading.Event(), threading.Event())
        assert opts["concurrent_fragment_downloads"] == 6

    def test_configuracion_view_fragments_persistence(self, qapp) -> None:
        class DummySettingsRepo:
            def __init__(self):
                self.store = {"concurrent_fragments": 6}

            def get_all(self):
                return self.store

            def set(self, key, value, data_type, category):
                self.store[key] = value

        repo = DummySettingsRepo()
        view = ConfiguracionView(settings_repo=repo)
        assert hasattr(view, "spin_fragments")
        assert view.spin_fragments.value() == 6

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            view.spin_fragments.setValue(8)
            view._on_save_clicked()

        assert repo.store["concurrent_fragments"] == 8

    def test_main_view_model_applies_fragments(self) -> None:
        vm = MainViewModel(
            platform_adapter=MagicMock(),
            download_engine=MagicMock(),
            repository=MagicMock(),
            event_bus=MagicMock(),
        )
        vm.apply_settings({"concurrent_fragments": 7})
        vm.download_engine.set_concurrent_fragments.assert_called_once_with(7)


class TestDragAndDrop:

    def test_can_accept_drag_url(self, qapp) -> None:
        view = InicioView()
        mime = QMimeData()
        mime.setText("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        class DummyDragEvent:
            def mimeData(self):
                return mime

        assert view._can_accept_drag(DummyDragEvent()) is True

    def test_extract_urls_from_text(self, qapp) -> None:
        view = InicioView()
        mime = QMimeData()
        mime.setText("https://vimeo.com/123\nhttps://reddit.com/r/video/456")

        urls = view._extract_urls_from_mime(mime)
        assert len(urls) == 2
        assert urls[0] == "https://vimeo.com/123"
        assert urls[1] == "https://reddit.com/r/video/456"

    def test_extract_urls_from_txt_file(self, qapp) -> None:
        view = InicioView()
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("https://twitter.com/user/status/1\n")
            f.write("  \n")
            f.write("https://soundcloud.com/artist/track\n")
            temp_path = f.name

        try:
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(temp_path)])

            urls = view._extract_urls_from_mime(mime)
            assert len(urls) == 2
            assert urls[0] == "https://twitter.com/user/status/1"
            assert urls[1] == "https://soundcloud.com/artist/track"
        finally:
            if os.path.isfile(temp_path):
                os.remove(temp_path)

    def test_set_drag_feedback_toggles_property(self, qapp) -> None:
        view = InicioView()
        view._set_drag_feedback(True)
        assert view.url_bar.property("drag_active") == "true"

        view._set_drag_feedback(False)
        assert view.url_bar.property("drag_active") == "false"
