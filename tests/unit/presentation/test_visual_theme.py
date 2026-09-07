"""Pruebas del sistema de diseño visual y componentes nuevos del rediseño profundo."""

import pytest
from PySide6.QtWidgets import QApplication

from src.presentation.components.title_bar import TitleBar
from src.presentation.styles.styles import DARK_PALETTE, DARK_STYLE, LIGHT_PALETTE, build_qss


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestThemeTokens:

    def test_dark_style_generated_from_palette(self):
        assert DARK_STYLE == build_qss(DARK_PALETTE)

    def test_palettes_expose_same_token_schema(self):
        dark_fields = set(DARK_PALETTE.__dataclass_fields__)
        light_fields = set(LIGHT_PALETTE.__dataclass_fields__)
        assert dark_fields == light_fields

    def test_qss_contains_core_selectors(self):
        for selector in (
            "QWidget#TitleBar",
            "QPushButton#NavButton:checked",
            "QPushButton#DownloadButton",
            "QPushButton#SegmentButton:checked",
            "QFrame#QualityCard[selected=\"true\"]",
            "QLineEdit#UrlInput[property~=\"invalid\"]",
            "QFrame#ClipboardBanner",
            "QLabel#StatusLabel[state=\"error\"]",
            "QLabel#SpeedLabel",
            "QMenu",
            "QMenu::item:selected",
        ):
            assert selector in DARK_STYLE, f"Falta el selector {selector}"

    def test_accent_reserved_for_actions(self):
        # El verde de marca debe aparecer en botones de acción clave.
        assert "QPushButton#PrimaryButton" in DARK_STYLE
        assert "QPushButton#DownloadButton" in DARK_STYLE


class TestTitleBar:

    def _make(self, qapp) -> TitleBar:
        return TitleBar()

    def test_fixed_height_and_object_name(self, qapp):
        bar = self._make(qapp)
        assert bar.objectName() == "TitleBar"
        assert bar.height() == TitleBar.HEIGHT

    def test_signals_emitted_by_buttons(self, qapp):
        bar = self._make(qapp)
        received = {"min": 0, "max": 0, "close": 0}
        bar.minimize_requested.connect(lambda: received.__setitem__("min", received["min"] + 1))
        bar.maximize_toggle_requested.connect(lambda: received.__setitem__("max", received["max"] + 1))
        bar.close_requested.connect(lambda: received.__setitem__("close", received["close"] + 1))
        bar.btn_minimize.click()
        bar.btn_maximize.click()
        bar.btn_close.click()
        assert received == {"min": 1, "max": 1, "close": 1}

    def test_is_drag_zone_excludes_buttons(self, qapp):
        from PySide6.QtCore import QPoint

        bar = self._make(qapp)
        center = QPoint(bar.width() // 4, bar.height() // 2)
        over_close = bar.btn_close.geometry().center()
        assert bar.is_drag_zone(center) is True
        assert bar.is_drag_zone(over_close) is False

    def test_window_state_icon_refresh(self, qapp):
        bar = self._make(qapp)
        tooltip_max = bar.btn_maximize.toolTip()
        bar.refresh_window_state_icon(maximized=True)
        assert bar.btn_maximize.toolTip() == "Restaurar"
        assert tooltip_max == "Maximizar"


class TestThemeSynchronization:

    def test_theme_switching_tracks_current_palette(self, qapp):
        from src.presentation.styles.theme import (
            DARK_PALETTE,
            LIGHT_PALETTE,
            OLED_PALETTE,
            get_current_palette,
            get_current_theme,
            get_theme_qss,
        )

        get_theme_qss("Claro Moderno")
        assert get_current_theme() == "Claro Moderno"
        assert get_current_palette() == LIGHT_PALETTE

        get_theme_qss("Oscuro OLED")
        assert get_current_theme() == "Oscuro OLED"
        assert get_current_palette() == OLED_PALETTE

        get_theme_qss("Oscuro Multimedia (Default)")
        assert get_current_theme() == "Oscuro Multimedia (Default)"
        assert get_current_palette() == DARK_PALETTE

    def test_thumbnail_label_reacts_to_theme_change(self, qapp):
        from PySide6.QtCore import QEvent
        from src.presentation.components.thumbnail_loader import ThumbnailLabel
        from src.presentation.styles.theme import get_theme_qss

        label = ThumbnailLabel(display_width=160, display_height=90)
        get_theme_qss("Claro Moderno")
        label.changeEvent(QEvent(QEvent.Type.StyleChange))
        label.repaint()
        assert label._placeholder_text == ThumbnailLabel.LOADING_TEXT

        get_theme_qss("Oscuro Multimedia (Default)")
        label.changeEvent(QEvent(QEvent.Type.StyleChange))
        label.repaint()
