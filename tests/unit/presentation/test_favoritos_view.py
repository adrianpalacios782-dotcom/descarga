import pytest
from PySide6.QtWidgets import QApplication

from src.domain.entities.favorite_item import FavoriteItem
from src.presentation.components.content_preview_card import ContentPreviewCard
from src.presentation.views.favoritos_view import FavoritosView, FavoriteCard


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_item():
    return FavoriteItem(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Rick Astley - Never Gonna Give You Up",
        author="Rick Astley",
        platform="YouTube",
        duration_seconds=212.0,
        thumbnail_url="",
    )


def test_favoritos_view_empty_state(qapp):
    view = FavoritosView()
    assert view.empty_card.isHidden() is False
    assert view.scroll_area.isHidden() is True
    assert view.lbl_count.text() == ""


def test_favoritos_view_load_items(qapp, sample_item):
    view = FavoritosView()
    view.load_favorites([sample_item])

    assert view.empty_card.isHidden() is True
    assert view.scroll_area.isHidden() is False
    assert "1 contenido" in view.lbl_count.text()


def test_favoritos_card_signals(qapp, sample_item):
    view = FavoritosView()
    downloads = []
    removes = []

    view.download_requested.connect(lambda u: downloads.append(u))
    view.remove_requested.connect(lambda u: removes.append(u))

    view.load_favorites([sample_item])

    # Encontrar la tarjeta instanciada
    card = view.cards_container.findChild(FavoriteCard)
    assert card is not None

    # Simular clic en Descargar y Eliminar
    for btn in card.findChildren(object):
        if getattr(btn, "text", lambda: "")() == "▶ Descargar":
            btn.click()
        elif getattr(btn, "text", lambda: "")() == "Eliminar":
            btn.click()

    assert len(downloads) == 1
    assert downloads[0] == sample_item.url
    assert len(removes) == 1
    assert removes[0] == sample_item.url


def test_content_preview_card_favorite_toggle(qapp):
    card = ContentPreviewCard()
    assert card.btn_favorite.isVisible() is False

    toggled_states = []
    card.favorite_toggled.connect(lambda s: toggled_states.append(s))

    # Marcar como favorito externamente
    card.set_is_favorite(True)
    assert card._is_favorite is True
    assert "En Favoritos" in card.btn_favorite.text()

    # Clic en botón toggle
    card.btn_favorite.click()
    assert card._is_favorite is False
    assert len(toggled_states) == 1
    assert toggled_states[0] is False
