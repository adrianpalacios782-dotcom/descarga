"""Indicador automático de estado de sesión en la vista de inicio.

El banner "¿Esperabas calidades superiores? Cargar cookies.txt" se sustituyó
por un indicador que informa de si la app está usando la sesión del navegador
detectada automáticamente:

- ``LINKED``: sesión vinculada -> se informa y el botón de cookies.txt se
  OCULTA (ya no hace falta cargar nada a mano).
- ``BLOCKED``: el navegador está abierto y Windows bloquea su almacén de
  cookies -> se explica cómo resolverlo y el botón queda como último recurso.
- ``UNAVAILABLE``: no hay navegador con perfil activo -> se informa y el botón
  queda disponible.
"""

import os
import sys

import pytest
from PySide6.QtWidgets import QApplication

from src.domain.entities.format_option import AudioFormat, VideoQualityOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.session_status import SessionState, SessionStatus
from src.domain.value_objects.url import Url
from src.presentation.views.inicio_view import InicioView


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


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
    ]
    fields = dict(
        media_id=MediaId.from_string(url.value),
        url=url,
        platform="YouTube",
        title="Video de Prueba",
        author="Canal Oficial",
        description="Descripción corta del contenido.",
        duration_seconds=512.0,
        thumbnail_url="https://i.ytimg.com/vi/abc/maxresdefault.jpg",
        upload_date="20240815",
        video_quality_options=options,
        audio_formats=[
            AudioFormat(
                format_id="140",
                extension="m4a",
                bitrate_kbps=128.0,
                filesize_bytes=8 * 1024 * 1024,
            )
        ],
    )
    fields.update(overrides)
    return MediaMetadata(**fields)


class TestSessionIndicator:
    """El estado de sesión se comunica en la vista de calidades."""

    def test_a_linked_session_is_reported_and_hides_the_cookies_button(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(
            make_metadata(
                session_status=SessionStatus(
                    state=SessionState.LINKED, browser="chrome", profile="Default"
                )
            )
        )

        text = view.lbl_format_hint.text()
        assert "Sesión vinculada automáticamente" in text
        assert "Chrome" in text
        assert "Default" in text
        assert view.btn_load_cookies.isHidden(), (
            "Con la sesión vinculada no debe ofrecerse cargar cookies.txt"
        )

    def test_a_blocked_session_explains_that_the_browser_must_be_closed(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(
            make_metadata(
                session_status=SessionStatus(
                    state=SessionState.BLOCKED, browser="chrome", profile="Default"
                )
            )
        )

        text = view.lbl_format_hint.text()
        assert "No se pudo vincular la sesión" in text
        assert "Chrome" in text
        assert "Ciérralo por completo" in text
        assert not view.btn_load_cookies.isHidden(), (
            "Sin sesión el cookies.txt queda como último recurso"
        )

    def test_an_unavailable_session_is_reported(self, qapp) -> None:
        view = InicioView()
        view.set_metadata(
            make_metadata(session_status=SessionStatus(state=SessionState.UNAVAILABLE))
        )

        text = view.lbl_format_hint.text()
        assert "No se encontró ningún navegador" in text
        assert not view.btn_load_cookies.isHidden()

    def test_the_old_banner_is_not_shown_when_there_is_a_session_status(self, qapp) -> None:
        """El banner que pedía cookies.txt ya no aparece: lo sustituye el
        indicador de sesión."""
        view = InicioView()
        view.set_metadata(
            make_metadata(
                session_status=SessionStatus(
                    state=SessionState.LINKED, browser="chrome", profile="Default"
                )
            )
        )

        assert "¿Esperabas calidades superiores" not in view.lbl_format_hint.text()

    def test_the_warning_of_the_analysis_has_priority(self, qapp) -> None:
        """Si la extracción se degradó, el aviso explica por qué: es más útil
        que el estado de sesión."""
        view = InicioView()
        view.set_metadata(
            make_metadata(
                warning_message="No se pudieron leer las cookies de 'chrome'.",
                session_status=SessionStatus(
                    state=SessionState.BLOCKED, browser="chrome", profile="Default"
                ),
            )
        )

        assert "No se pudieron leer las cookies" in view.lbl_format_hint.text()
        assert not view.btn_load_cookies.isHidden()

    def test_without_session_status_the_old_behaviour_is_kept(self, qapp) -> None:
        """Sin información de sesión (otras plataformas) no se inventa nada."""
        view = InicioView()
        view.set_metadata(make_metadata())

        assert view.lbl_format_hint.text() == ""
        assert view.btn_load_cookies.isHidden()


class TestSessionHintText:
    """El texto del indicador es el contrato de la vista."""

    def test_the_browser_name_is_human_readable(self) -> None:
        status = SessionStatus(state=SessionState.LINKED, browser="brave", profile="Perfil 1")
        text = InicioView._session_hint_text(status)
        assert "Brave" in text
        assert "Perfil 1" in text

    def test_an_unknown_browser_does_not_break_the_text(self) -> None:
        status = SessionStatus(state=SessionState.LINKED, browser="otro")
        assert "otro" in InicioView._session_hint_text(status)
