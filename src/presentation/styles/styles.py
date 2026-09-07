"""Hoja de estilos de la aplicacion.

El QSS se genera desde tokens centralizados en theme.py, preparado para
soportar un modo claro en el futuro sin tocar las vistas.
"""

from src.presentation.styles.theme import (
    DARK_PALETTE,
    DARK_STYLE,
    LIGHT_PALETTE,
    OLED_PALETTE,
    THEME_PALETTES,
    Palette,
    build_qss,
    get_current_palette,
    get_current_theme,
    get_theme_palette,
    get_theme_qss,
    set_current_theme,
)

__all__ = [
    "DARK_PALETTE",
    "DARK_STYLE",
    "LIGHT_PALETTE",
    "OLED_PALETTE",
    "THEME_PALETTES",
    "Palette",
    "build_qss",
    "get_current_palette",
    "get_current_theme",
    "get_theme_palette",
    "get_theme_qss",
    "set_current_theme",
]
