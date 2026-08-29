"""Pruebas unitarias para las nuevas capacidades de la pantalla de análisis y descarga.

Verifica:
- Formato estructurado en tabla (FormatTableRow con columnas: calidad, formato, tamaño, códec, fps, estado).
- Campo de nombre de archivo editable y su correcta propagación a la ruta de descarga.
- Comportamiento del indicador circular visible y selección de fila completa.
- Visibilidad e integración del disclaimer de tamaño aproximado.
"""

import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.domain.entities.format_option import AudioFormat, VideoQualityOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.presentation.components.format_table_widget import FormatTableRow
from src.presentation.views.inicio_view import InicioView


@pytest.fixture(scope="module")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _make_dummy_metadata(title="Video Especial 2026"):
    url = Url("https://www.youtube.com/watch?v=12345678901")
    options = [
        VideoQualityOption(
            height=1080,
            label="1080p",
            badge="HD",
            video_format_id="137+140",
            audio_format_id="140",
            needs_ffmpeg_merge=True,
            estimated_size_bytes=65 * 1024 * 1024,
            fps=60.0,
            extension="mp4",
            video_codec="avc1.64002a",
            is_best_quality=True,
        ),
        VideoQualityOption(
            height=720,
            label="720p",
            badge="HD",
            video_format_id="136+140",
            audio_format_id="140",
            needs_ffmpeg_merge=True,
            estimated_size_bytes=35 * 1024 * 1024,
            fps=30.0,
            extension="mp4",
            video_codec="vp9",
        ),
    ]
    audio_formats = [
        AudioFormat(
            format_id="140",
            extension="m4a",
            bitrate_kbps=128.0,
            audio_codec="mp4a.40.2",
            filesize_bytes=5 * 1024 * 1024,
        )
    ]
    return MediaMetadata(
        media_id=MediaId.from_string(url.value),
        url=url,
        platform="YouTube",
        title=title,
        author="Canal Pruebas",
        description="Descripción corta del video de pruebas.",
        duration_seconds=340.0,
        thumbnail_url="https://img.youtube.com/vi/123/hqdefault.jpg",
        upload_date="20260115",
        video_quality_options=options,
        audio_formats=audio_formats,
    )


class TestInicioViewEnhanced:

    def test_custom_editable_filename_used_in_download_request(self, qapp, tmp_path):
        """Si el usuario edita el nombre del archivo, se utiliza ese nombre en la descarga."""
        view = InicioView()
        metadata = _make_dummy_metadata(title="Título Original de YouTube")
        view.set_metadata(metadata)
        view.txt_dest.setText(str(tmp_path))

        # Verificar que se inicializó con el título sugerido
        assert "Título Original de YouTube" in view.txt_filename.text()

        # Usuario cambia el nombre del archivo
        view.txt_filename.setText("Mi_Video_Personalizado")

        captured = {}
        view.download_requested.connect(lambda m, f, d: captured.update(fmt=f, dest=d))
        view._on_download_clicked()

        assert "Mi_Video_Personalizado" in captured["dest"]
        assert captured["dest"].endswith(" - Mejor calidad.mp4")

    def test_format_table_row_columns_displayed(self, qapp):
        """Las filas muestran columnas de calidad, formato, tamaño, códec, fps y badge."""
        metadata = _make_dummy_metadata()
        vqo = metadata.video_quality_options[0]
        row = FormatTableRow(vqo=vqo, is_recommended=True)

        assert row.lbl_quality.text() == "1080p"
        assert row.lbl_format.text() == "MP4"
        assert "65.0 MB" in row.size_label.text()
        assert "AVC1" in row.lbl_codec.text()
        assert "60 FPS" in row.lbl_fps.text()
        assert row.lbl_rec_badge.text() == "Recomendado"
        assert not row.radio.isChecked()

        # Clic en la fila activa el selector
        row.radio.setChecked(True)
        assert row.property("selected") is True

    def test_size_estimate_includes_approximate_note(self, qapp):
        """La vista aclara que el tamaño es aproximado."""
        view = InicioView()
        metadata = _make_dummy_metadata()
        view.set_metadata(metadata)

        assert "El tamaño es aproximado." in view.lbl_size_note.text()
        assert "~65.0 MB" in view.lbl_size_estimate.text()
