import pytest
from PySide6.QtWidgets import QApplication

from src.domain.entities.subtitle import SubtitleMode, SubtitleTrack
from src.presentation.components.content_preview_card import ContentPreviewCard


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_preview_card_populate_subtitles_empty(qapp):
    card = ContentPreviewCard()
    card.populate_subtitles([])

    assert card.combo_subtitles.count() == 1
    assert card.combo_subtitles.itemText(0) == "Sin subtítulos"
    assert card.combo_subtitles.isEnabled() is False
    assert card.chk_embed_sub.isEnabled() is False

    cfg = card.get_subtitle_config()
    assert cfg.mode == SubtitleMode.NONE


def test_preview_card_populate_subtitles_with_tracks(qapp):
    card = ContentPreviewCard()
    tracks = [
        SubtitleTrack(language_code="es", name="Español"),
        SubtitleTrack(language_code="en", name="English", is_auto_generated=True),
    ]
    card.populate_subtitles(tracks)

    assert card.combo_subtitles.count() == 3
    assert card.combo_subtitles.isEnabled() is True
    assert card.chk_embed_sub.isEnabled() is True

    # Seleccionar Español (índice 1)
    card.combo_subtitles.setCurrentIndex(1)
    card.chk_embed_sub.setChecked(True)

    cfg = card.get_subtitle_config()
    assert cfg.mode == SubtitleMode.EMBED
    assert cfg.language_code == "es"
    assert cfg.is_auto_generated is False

    # Cambiar a modo externo
    card.chk_embed_sub.setChecked(False)
    cfg_ext = card.get_subtitle_config()
    assert cfg_ext.mode == SubtitleMode.EXTERNAL
