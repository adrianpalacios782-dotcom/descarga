"""Hoja de estilos de la aplicacion.

El QSS se genera desde tokens centralizados en theme.py, preparado para
soportar un modo claro en el futuro sin tocar las vistas.
"""

from src.presentation.styles.theme import (
    DARK_PALETTE,
    DARK_STYLE,
    LIGHT_PALETTE,
    Palette,
    build_qss,
)

__all__ = [
    "DARK_PALETTE",
    "DARK_STYLE",
    "LIGHT_PALETTE",
    "Palette",
    "build_qss",
]
