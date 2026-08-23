import os
import sys
import time

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from src.domain.entities.format_option import AudioFormat, VideoQualityOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.presentation.components.thumbnail_loader import ThumbnailLabel
from src.presentation.views.inicio_view import InicioView


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


LONG_DESCRIPTION = (
    "Esta es una descripción extraordinariamente larga que supera con claridad el límite "
    "de caracteres permitido para la sinopsis resumida. " * 4
)


def make_metadata(**overrides) -> MediaMetadata:
    url = Url("https://www.youtube.com/watch?v=abc12345678")
    options = [
        VideoQualityOption(
            height=1080,
            label="Mejor calidad",
            badge="HD",
            video_format_id="137+140",
            audio_format_id="140",
            needs_ffmpeg_merge=True,
            estimated_size_bytes=84 * 1024 * 1024,
            fps=30.0,
            extension="mp4",
            is_best_quality=True,
        ),
        VideoQualityOption(
            height=720,
            label="720p",
            badge="",
            video_format_id="136+140",
            audio_format_id="140",
            needs_ffmpeg_merge=True,
            estimated_size_bytes=48 * 1024 * 1024,
            fps=30.0,
            extension="mp4",
        ),
        VideoQualityOption(
            height=480,
            label="480p",
            badge="",
            video_format_id="135+140",
            audio_format_id="140",
            needs_ffmpeg_merge=True,
            estimated_size_bytes=None,
            fps=30.0,
            extension="mp4",
        ),
    ]
    fields = dict(
        media_id=MediaId.from_string(url.value),
        url=url,
        platform="YouTube",
        title="Video de Prueba Completo",
        author="Canal Oficial",
        description="Descripción corta del contenido.",
        duration_seconds=512.0,
        thumbnail_url="https://i.ytimg.com/vi/abc/maxresdefault.jpg",
        upload_date="20240815",
        video_quality_options=options,
        audio_formats=[AudioFormat(format_id="140", extension="m4a", bitrate_kbps=128.0, filesize_bytes=8 * 1024 * 1024)],
    )
    fields.update(overrides)
    return MediaMetadata(**fields)


class TestInicioViewStates:

    def test_initial_state_is_empty_and_card_hidden(self, qapp) -> None:
        view = InicioView()
        assert view.lbl_status.property("state") == "empty"
        assert view.lbl_status.text() == "Listo para descargar"
        assert view.preview_card.isHidden()

    def test_analyzing_state_disables_controls_and_shows_banner(self, qapp) -> None:
        view = InicioView()
        view.set_analyzing_state(True)
        assert not view.btn_analyze.isEnabled()
        assert view.btn_analyze.text() == "Analizando..."
        assert not view.url_input.isEnabled()
        assert view.lbl_status.property("state") == "analyzing"
        assert view.preview_card.isHidden()

    def test_set_metadata_shows_success_banner_chips_and_card(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata())
        assert view.lbl_status.property("state") == "success"
        assert view.lbl_status.text() == "Contenido encontrado"
        assert not view.preview_card.isHidden()
        assert view.chip_platform.text() == "YouTube"
        assert not view.chip_platform.isHidden()
        assert view.chip_year.text() == "Publicado en 2024"
        assert not view.chip_year.isHidden()
        assert view.chip_duration.text() == "Duración 08:32"
        assert not view.btn_analyze.isEnabled() or view.btn_analyze.text() == "Analizar"

    def test_missing_upload_date_hides_year_chip(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata(upload_date=""))
        assert view.chip_year.isHidden()

    def test_missing_duration_hides_duration_chip(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata(duration_seconds=0.0))
        assert view.chip_duration.isHidden()

    def test_long_synopsis_truncated_with_ver_mas_toggle(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata(description=LONG_DESCRIPTION))
        shown = view.lbl_synopsis.text()
        assert len(shown) < len(LONG_DESCRIPTION.strip())
        assert shown.endswith("...")
        assert not view.btn_toggle_synopsis.isHidden()
        assert view.btn_toggle_synopsis.text() == "Ver más"

        view.btn_toggle_synopsis.click()
        assert view.lbl_synopsis.text().startswith("Esta es una descripción")
        assert view.btn_toggle_synopsis.text() == "Ver menos"

    def test_empty_synopsis_fallback(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata(description="   "))
        assert view.lbl_synopsis.text() == "Sin descripción disponible."
        assert view.btn_toggle_synopsis.isHidden()

    def test_quality_rows_built_from_real_formats_first_selected(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata())
        rows = list(view._iter_quality_rows())
        assert len(rows) == 3
        assert rows[0].radio.isChecked()
        assert "Tamaño estimado" in view.lbl_size_estimate.text()
        assert "~84.0 MB" in view.lbl_size_estimate.text()

    def test_selecting_option_without_size_shows_unavailable(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata())
        rows = list(view._iter_quality_rows())
        rows[2].radio.setChecked(True)
        assert "no disponible" in view.lbl_size_estimate.text()

    def test_audio_mode_switches_panels(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata())
        view.btn_format_audio.setChecked(True)
        assert not view.panel_audio.isHidden()
        assert view.selected_type.name == "AUDIO"

    def test_audio_only_media_auto_selects_mp3(self, qapp) -> None:
        metadata = make_metadata(video_quality_options=[], video_formats=[])
        view = InicioView()
        view.set_metadata(metadata)
        assert view.btn_format_audio.isChecked()
        assert not view.panel_audio.isHidden()


class TestInicioDownloadFlow:

    def _capture(self, view):
        captured = {}
        view.download_requested.connect(lambda m, f, d: captured.update(fmt=f, dest=d))
        return captured

    def test_download_emits_best_quality_video_signal(self, qapp, tmp_path) -> None:
        view = InicioView()
        view.set_metadata(make_metadata())
        view.txt_dest.setText(str(tmp_path))
        captured = self._capture(view)

        view._on_download_clicked()
        assert captured["fmt"] == "vq_best"
        assert captured["dest"].endswith(" - Mejor calidad.mp4")

    def test_download_emits_height_based_video_signal(self, qapp, tmp_path) -> None:
        view = InicioView()
        view.set_metadata(make_metadata())
        view.txt_dest.setText(str(tmp_path))
        rows = list(view._iter_quality_rows())
        rows[1].radio.setChecked(True)
        captured = self._capture(view)

        view._on_download_clicked()
        assert captured["fmt"] == "vq_720"
        assert captured["dest"].endswith(" - 720p.mp4")

    def test_invalid_destination_warns_without_signal(self, qapp, monkeypatch) -> None:
        calls = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a)))
        view = InicioView()
        view.set_metadata(make_metadata())
        view.txt_dest.setText(r"C:\__directorio_que_no_existe_osvaldo__")
        captured = self._capture(view)

        view._on_download_clicked()
        assert len(calls) == 1
        assert captured == {}


class TestInicioErrorStates:

    def test_show_error_sets_error_banner_and_hides_card(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(make_metadata())
        assert not view.preview_card.isHidden()

        view.show_error("Fallo al analizar el contenido multimedia: video privado")
        assert view.lbl_status.property("state") == "error"
        assert "No pudimos analizar este enlace" in view.lbl_status.text()
        assert "El enlace no es compatible o la plataforma no respondió." in view.lbl_status.text()
        assert "video privado" in view.lbl_status.text()
        assert view.preview_card.isHidden()

    def test_error_message_never_shows_traceback(self, qapp) -> None:
        view = InicioView()
        dirty = 'Traceback (most recent call last):\n  File "x.py"\nERROR: boom'
        view.show_error(dirty)
        banner = view.lbl_status.text()
        assert "Traceback" not in banner
        assert ".py" not in banner

    def test_recovery_after_error_returns_to_empty_state(self, qapp) -> None:
        view = InicioView()
        view.show_error("fallo temporal")
        view.set_analyzing_state(False)
        assert view.lbl_status.property("state") == "empty"


class TestInicioNoQualitiesFlow:
    """Problemas 4 y 5: sin calidades no se inicia descarga; validación inline, sin QMessageBox."""

    def _assert_no_qmessagebox(self, monkeypatch) -> list:
        calls = []

        def _forbidden(*a, **k):
            calls.append((a, k))
            raise AssertionError("QMessageBox prohibido para validación de selección")

        from PySide6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(_forbidden))
        monkeypatch.setattr(QMessageBox, "information", staticmethod(_forbidden))
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(_forbidden))
        return calls

    def test_no_video_qualities_disables_download_and_shows_inline_reason(self, qapp, monkeypatch) -> None:
        self._assert_no_qmessagebox(monkeypatch)
        metadata = make_metadata(video_quality_options=[], video_formats=[])
        view = InicioView()
        view.set_metadata(metadata)

        # Con audio disponible el modo AUDIO se auto-selecciona: simulamos modo VIDEO manual.
        view.btn_format_video.setChecked(True)
        assert not view.btn_download.isEnabled()
        assert "no ofrece calidades de video" in view.lbl_selection_summary.text()

    def test_clicking_disabled_download_never_emits_signal(self, qapp, monkeypatch, tmp_path) -> None:
        self._assert_no_qmessagebox(monkeypatch)
        metadata = make_metadata(video_quality_options=[], video_formats=[])
        view = InicioView()
        view.set_metadata(metadata)
        view.btn_format_video.setChecked(True)
        view.txt_dest.setText(str(tmp_path))

        captured = []
        view.download_requested.connect(lambda m, f, d: captured.append(f))
        view._on_download_clicked()
        assert captured == [], "Sin selección de calidad NO debe iniciarse descarga"

    def test_no_qmessagebox_for_missing_quality_selection(self, qapp, monkeypatch, tmp_path) -> None:
        """Caso obligatorio 13: el caso 'Selección Requerida' ya nunca usa QMessageBox."""
        self._assert_no_qmessagebox(monkeypatch)
        metadata = make_metadata(video_quality_options=[], video_formats=[])
        view = InicioView()
        view.set_metadata(metadata)
        view.btn_format_video.setChecked(True)
        view.txt_dest.setText(str(tmp_path))
        captured = []
        view.download_requested.connect(lambda m, f, d: captured.append(f))
        view._on_download_clicked()
        assert captured == []

    def test_with_qualities_button_enabled_and_best_preselected(self, qapp, monkeypatch) -> None:
        """Caso obligatorio 9 (UI): con calidades, 'Mejor calidad' queda preseleccionada."""
        self._assert_no_qmessagebox(monkeypatch)
        view = InicioView()
        view.set_metadata(make_metadata())
        assert view.btn_download.isEnabled()
        rows = list(view._iter_quality_rows())
        assert rows[0].radio.isChecked()
        assert rows[0].vqo.is_best_quality

    def test_audio_mode_without_audio_formats_disables_button(self, qapp, monkeypatch) -> None:
        self._assert_no_qmessagebox(monpatch := monkeypatch)
        metadata = make_metadata(audio_formats=[])
        view = InicioView()
        view.set_metadata(metadata)
        view.btn_format_audio.setChecked(True)
        assert not view.btn_download.isEnabled()
        assert "pistas de audio" in view.lbl_selection_summary.text()

    def test_card_without_size_shows_tamano_no_disponible(self, qapp) -> None:
        """Caso obligatorio 2 (UI): formato sin filesize aparece con 'Tamaño no disponible'."""
        view = InicioView()
        view.set_metadata(make_metadata())
        row_480 = list(view._iter_quality_rows())[2]
        tech = row_480.info.text()
        assert "Tamaño no disponible" in tech
        assert row_480.vqo.estimated_size_bytes is None


class TestThumbnailFallback:

    def _wait_for(self, condition, timeout_s=3.0) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            QApplication.processEvents()
            if condition():
                return True
            time.sleep(0.05)
        return False

    def test_broken_thumbnail_shows_placeholder(self, qapp, monkeypatch) -> None:
        from src.presentation.components.thumbnail_loader import clear_thumbnail_cache

        clear_thumbnail_cache()

        def broken_fetch(url):
            raise RuntimeError("thumbnail rota")

        monkeypatch.setattr(
            "src.presentation.components.thumbnail_loader.fetch_thumbnail", broken_fetch
        )
        thumb = ThumbnailLabel(160, 90)
        thumb.load_from_url("https://i.ytimg.com/broken-unit-test/maxresdefault.jpg")
        assert self._wait_for(lambda: thumb._placeholder_text == "Sin vista previa")

    def test_empty_url_shows_clean_placeholder(self, qapp) -> None:
        thumb = ThumbnailLabel(160, 90)
        thumb.load_from_url("")
        assert thumb._placeholder_text == ""
