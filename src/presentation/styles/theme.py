"""Sistema de diseño centralizado: paletas como tokens y constructor de QSS.

Arquitectura preparada para modo claro: cualquier paleta que exponga los mismos
atributos puede alimentar build_qss(). El acento verde se reserva para acciones
importantes (Analizar/Descargar/progreso/selección/estados positivos).
"""

from dataclasses import dataclass


# ------------------------------------------------------------------ Tokens
# Escalas compartidas por todas las vistas: nada de valores arbitrarios.
SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "page_x": 36,
    "page_y": 30,
}

RADIUS = {
    "sm": 6,
    "md": 10,
    "lg": 14,
    "pill": 16,
}

FONT_SIZE = {
    "micro": 10,
    "xs": 11,
    "sm": 12,
    "base": 13,
    "md": 14,
    "lg": 15,
    "xl": 19,
    "title": 24,
    "hero": 30,
}


@dataclass(frozen=True)
class Palette:
    """Tokens de color de la aplicación."""

    # Fondos
    bg_window: str
    bg_sidebar: str
    bg_titlebar: str
    surface: str            # tarjetas / paneles
    surface_hover: str
    surface_active: str     # elemento seleccionado (nav, calidad)
    surface_sunken: str     # inputs, listas internas

    # Bordes
    border: str
    border_strong: str
    border_focus: str

    # Texto
    text_primary: str
    text_secondary: str
    text_tertiary: str
    text_on_accent: str

    # Acento (acciones importantes únicamente)
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_dim: str         # fondo translúcido del acento
    accent_text: str        # texto coloreado sobre superficie

    # Semánticos
    danger: str
    warning: str

    # Ventana
    close_hover_bg: str


DARK_PALETTE = Palette(
    bg_window="#0e0e11",
    bg_sidebar="#101013",
    bg_titlebar="#101013",
    surface="#16161a",
    surface_hover="#1c1c21",
    surface_active="#232329",
    surface_sunken="#121216",
    border="#242429",
    border_strong="#303038",
    border_focus="#1db954",
    text_primary="#f2f2f4",
    text_secondary="#a4a4ad",
    text_tertiary="#6d6d76",
    text_on_accent="#06130a",
    accent="#1db954",
    accent_hover="#1ed760",
    accent_pressed="#169c46",
    accent_dim="rgba(29, 185, 84, 0.10)",
    accent_text="#1ed760",
    danger="#ff6b6b",
    warning="#f59e0b",
    close_hover_bg="#e81123",
)


LIGHT_PALETTE = Palette(
    bg_window="#f5f5f7",
    bg_sidebar="#eeeef1",
    bg_titlebar="#eeeef1",
    surface="#ffffff",
    surface_hover="#f2f2f5",
    surface_active="#e6e6ea",
    surface_sunken="#fafafa",
    border="#e2e2e6",
    border_strong="#cfced6",
    border_focus="#1db954",
    text_primary="#1a1a1e",
    text_secondary="#5c5c66",
    text_tertiary="#9a9aa2",
    text_on_accent="#ffffff",
    accent="#1db954",
    accent_hover="#22c55e",
    accent_pressed="#169c46",
    accent_dim="rgba(29, 185, 84, 0.10)",
    accent_text="#15803d",
    danger="#dc2626",
    warning="#b45309",
    close_hover_bg="#e81123",
)


def build_qss(p: Palette) -> str:
    """Genera la hoja de estilos completa a partir de una paleta y los tokens."""

    s = SPACING
    r = RADIUS
    fs = FONT_SIZE

    return f"""
/* ============================================================
   osvaldoDownloaderPro — tema generado desde tokens
   ============================================================ */

QMainWindow, QDialog {{
    background-color: {p.bg_window};
    color: {p.text_primary};
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}}

QWidget {{
    color: {p.text_primary};
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}}

QWidget:disabled {{ color: {p.text_tertiary}; }}

QToolTip {{
    background-color: {p.surface_active};
    color: {p.text_primary};
    border: 1px solid {p.border_strong};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ------------------------------------------------ Barra de título */
QWidget#TitleBar {{
    background-color: {p.bg_titlebar};
    border-bottom: 1px solid {p.border};
}}

QWidget#TitleBarDrag {{
    background-color: transparent;
}}

QLabel#TitleBrand {{
    color: {p.text_secondary};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}

QPushButton#WindowButton {{
    background-color: transparent;
    border: none;
    border-radius: 14px;
    margin: 0px 3px;
}}

QPushButton#WindowButton:hover {{
    background-color: {p.surface_active};
}}

QPushButton#WindowButton[property~="close"]:hover {{
    background-color: {p.close_hover_bg};
}}

/* ------------------------------------------------------- Sidebar */
QFrame#SidebarFrame {{
    background-color: {p.bg_sidebar};
    border-right: 1px solid {p.border};
}}

QLabel#SidebarTitle {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: {p.text_tertiary};
    padding: 0px 8px 10px 8px;
}}

QPushButton#NavButton {{
    background-color: transparent;
    color: {p.text_secondary};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
    spacing: 10px;
}}

QPushButton#NavButton:hover {{
    background-color: {p.surface_hover};
    color: {p.text_primary};
}}

QPushButton#NavButton:checked {{
    background-color: {p.surface_active};
    color: {p.accent_text};
    font-weight: 700;
    border-left: 3px solid {p.accent};
}}

QFrame#SidebarDivider {{
    background-color: {p.border};
    max-height: 1px;
    border: none;
    margin: 8px 10px;
}}

QLabel#SidebarGroupLabel {{
    font-size: {fs['micro']}px;
    font-weight: 800;
    letter-spacing: 1.2px;
    color: {p.text_tertiary};
    padding: 10px 8px 2px 8px;
}}

/* ------------------------------------------- Áreas desplazables */
QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

/* -------------------------------------------------------- Inputs */
QLineEdit {{
    background-color: {p.surface_sunken};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 10px 14px;
    color: {p.text_primary};
    font-size: 13px;
    selection-background-color: {p.accent};
    selection-color: {p.text_on_accent};
}}

QLineEdit:focus {{
    border: 1px solid {p.border_focus};
}}

QLineEdit#UrlInput {{
    font-size: 14px;
    padding: 12px 16px;
}}

QLineEdit#UrlInput[property~="invalid"] {{
    border: 1px solid {p.danger};
}}

QLineEdit#UrlInput[property~="valid"] {{
    border: 1px solid {p.border_strong};
}}

QComboBox {{
    background-color: {p.surface_sunken};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 9px 14px;
    color: {p.text_primary};
    font-size: 13px;
}}

QComboBox:hover {{
    border-color: {p.border_strong};
}}

QComboBox:focus {{
    border-color: {p.border_focus};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {p.text_tertiary};
    margin-right: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: {p.surface};
    selection-background-color: {p.surface_active};
    selection-color: {p.accent_text};
    color: {p.text_primary};
    border: 1px solid {p.border_strong};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QCheckBox {{
    spacing: 8px;
    color: {p.text_secondary};
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {p.border_strong};
    background-color: {p.surface_sunken};
}}

QCheckBox::indicator:checked {{
    background-color: {p.accent};
    border-color: {p.accent};
}}

QSpinBox {{
    background-color: {p.surface_sunken};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 6px 10px;
    color: {p.text_primary};
}}

/* --------------------------------------------- Botones primarios */
QPushButton#PrimaryButton {{
    background-color: {p.accent};
    color: {p.text_on_accent};
    border: none;
    border-radius: 10px;
    padding: 10px 26px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {p.accent_hover};
}}

QPushButton#PrimaryButton:pressed {{
    background-color: {p.accent_pressed};
}}

QPushButton#PrimaryButton:disabled {{
    background-color: {p.surface_active};
    color: {p.text_tertiary};
}}

QPushButton#DownloadButton {{
    background-color: {p.accent};
    color: {p.text_on_accent};
    border: none;
    border-radius: 12px;
    padding: 14px 32px;
    font-size: 15px;
    font-weight: 800;
}}

QPushButton#DownloadButton:hover {{
    background-color: {p.accent_hover};
}}

QPushButton#DownloadButton:pressed {{
    background-color: {p.accent_pressed};
}}

/* -------------------------------------------- Botones secundarios */
QPushButton#SecondaryButton {{
    background-color: {p.surface_hover};
    color: {p.text_primary};
    border: 1px solid {p.border_strong};
    border-radius: 9px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#SecondaryButton:hover {{
    background-color: {p.surface_active};
}}

QPushButton#SecondaryButton:disabled {{
    color: {p.text_tertiary};
    border-color: {p.border};
}}

QPushButton#SecondaryButton[danger="true"] {{
    color: {p.danger};
}}

QPushButton#SecondaryButton[danger="true"]:hover {{
    border-color: {p.danger};
}}

QPushButton#LinkButton {{
    background-color: transparent;
    border: none;
    color: {p.accent_text};
    font-size: 12px;
    font-weight: 600;
    padding: 2px 0px;
    text-align: left;
}}

QPushButton#LinkButton:hover {{
    text-decoration: underline;
}}

/* ------------------------------------ Selector segmentado V/A */
QWidget#SegmentContainer {{
    background-color: {p.surface_sunken};
    border: 1px solid {p.border};
    border-radius: 11px;
}}

QPushButton#SegmentButton {{
    background-color: transparent;
    color: {p.text_secondary};
    border: none;
    border-radius: 9px;
    padding: 7px 26px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#SegmentButton:hover {{
    color: {p.text_primary};
}}

QPushButton#SegmentButton:checked {{
    background-color: {p.surface_active};
    color: {p.text_primary};
}}

/* ------------------------------------- Chips de formato heredados */
QPushButton#FormatChip,
QPushButton#ModeButton {{
    background-color: {p.surface_sunken};
    color: {p.text_secondary};
    border: 1px solid {p.border};
    border-radius: 16px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#FormatChip:hover,
QPushButton#ModeButton:hover {{
    color: {p.text_primary};
    border-color: {p.border_strong};
}}

QPushButton#FormatChip:checked,
QPushButton#ModeButton:checked {{
    background-color: {p.surface_active};
    color: {p.text_primary};
    border-color: {p.accent};
}}

/* ------------------------------------------------------ Progreso */
QProgressBar {{
    border: none;
    background-color: {p.surface_active};
    border-radius: 3px;
    text-align: center;
    color: transparent;
    font-size: 11px;
}}

QProgressBar::chunk {{
    background-color: {p.accent};
    border-radius: 3px;
}}

/* ------------------------------------------------------ Tablas */
QTableWidget {{
    background-color: {p.surface};
    alternate-background-color: {p.surface};
    border: 1px solid {p.border};
    gridline-color: transparent;
    border-radius: 12px;
    outline: none;
}}

QTableWidget::item {{
    padding: 6px 10px;
    border-bottom: 1px solid {p.border};
}}

QTableWidget::item:selected {{
    background-color: {p.surface_active};
    color: {p.text_primary};
}}

QHeaderView::section {{
    background-color: {p.bg_window};
    color: {p.text_tertiary};
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid {p.border};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
}}

QTableCornerButton::section {{
    background-color: {p.bg_window};
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {p.border_strong};
    border-radius: 4px;
    min-height: 32px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.text_tertiary};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {p.border_strong};
    border-radius: 4px;
    min-width: 32px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* --------------------------------------------------- Contenedores */
QFrame#Card {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 14px;
    padding: 20px;
}}

QFrame#DownloadCard {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 12px;
    padding: 14px;
}}

QFrame#DownloadCard:hover {{
    border-color: {p.border_strong};
    background-color: {p.surface_hover};
}}

QFrame#EmptyStateCard {{
    background-color: {p.surface};
    border: 1px dashed {p.border_strong};
    border-radius: 16px;
    padding: 48px;
}}

QFrame#HeroCard {{
    background-color: transparent;
    border: none;
}}

/* -------------------------------------------------- Tipografía vista */
QLabel#ViewTitle {{
    font-size: 24px;
    font-weight: 800;
    color: {p.text_primary};
    letter-spacing: -0.2px;
}}

QLabel#ViewSubtitle {{
    font-size: 13px;
    color: {p.text_secondary};
}}

QLabel#HeroTitle {{
    font-size: 30px;
    font-weight: 800;
    color: {p.text_primary};
    letter-spacing: -0.4px;
}}

QLabel#HeroSubtitle {{
    font-size: 14px;
    color: {p.text_secondary};
}}

QLabel#PreviewTitle {{
    font-size: 19px;
    font-weight: 700;
    color: {p.text_primary};
}}

QLabel#PreviewChannel {{
    font-size: 13px;
    color: {p.text_secondary};
}}

QLabel#SectionHeader {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.4px;
    color: {p.text_tertiary};
}}

QLabel#SynopsisText {{
    font-size: 13px;
    color: {p.text_secondary};
    line-height: 150%;
}}

QLabel#FieldLabel {{
    font-size: 13px;
    font-weight: 600;
    color: {p.text_secondary};
}}

QLabel#HintLabel {{
    font-size: 12px;
    color: {p.text_tertiary};
}}

QLabel#SizeEstimate {{
    font-size: 12px;
    font-weight: 600;
    color: {p.text_secondary};
}}

QLabel#DownloadSummary {{
    font-size: 12px;
    color: {p.text_tertiary};
}}

/* ------------------------------------------------ Banner de estado */
QLabel#StatusLabel {{
    border-radius: 9px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid {p.border};
    background-color: {p.surface};
    color: {p.text_secondary};
}}

QLabel#StatusLabel[state="analyzing"] {{
    border: 1px solid {p.border_strong};
    color: {p.accent_text};
    background-color: {p.accent_dim};
}}

QLabel#StatusLabel[state="success"] {{
    border: 1px solid {p.accent};
    color: {p.accent_text};
    background-color: {p.accent_dim};
}}

QLabel#StatusLabel[state="error"] {{
    border: 1px solid {p.danger};
    color: {p.danger};
    background-color: rgba(255, 107, 107, 0.08);
}}

/* --------------------------------------------------------- Chips */
QLabel#Chip {{
    background-color: {p.surface_hover};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    color: {p.text_secondary};
}}

QLabel#ChipAccent {{
    background-color: {p.accent_dim};
    border: 1px solid {p.accent};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    color: {p.accent_text};
}}

QLabel#PlatformBadge {{
    font-size: 11px;
    color: {p.accent_text};
    font-weight: 700;
    background-color: {p.accent_dim};
    padding: 3px 8px;
    border-radius: 9px;
}}

/* ------------------------------------------------ Sugerencia portapapeles */
QFrame#ClipboardBanner {{
    background-color: {p.accent_dim};
    border: 1px solid {p.accent};
    border-radius: 10px;
}}

QLabel#ClipboardText {{
    color: {p.accent_text};
    font-size: 12px;
    font-weight: 600;
}}

/* ------------------------------------------- Tarjetas de calidad */
QFrame#QualityCard {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

QFrame#QualityCard:hover {{
    border-color: {p.border_strong};
    background-color: {p.surface_hover};
}}

QFrame#QualityCard[selected="true"] {{
    border: 1px solid {p.accent};
    background-color: {p.accent_dim};
}}

QRadioButton#QualityRadio {{
    background-color: transparent;
    color: {p.text_primary};
    font-size: 15px;
    font-weight: 700;
    spacing: 10px;
}}

QRadioButton#QualityRadio::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 8px;
    border: 2px solid {p.border_strong};
    background-color: {p.surface_sunken};
}}

QRadioButton#QualityRadio::indicator:hover {{
    border-color: {p.accent};
}}

QRadioButton#QualityRadio::indicator:checked {{
    border: 5px solid {p.accent};
    background-color: #ffffff;
}}

QLabel#QualityBadge {{
    background-color: {p.surface_active};
    color: {p.accent_text};
    font-size: 10px;
    font-weight: 800;
    padding: 2px 7px;
    border-radius: 8px;
}}

QLabel#QualityTechInfo {{
    font-size: 11px;
    color: {p.text_tertiary};
}}

QLabel#QualitySize {{
    font-size: 11px;
    font-weight: 600;
    color: {p.text_secondary};
}}

/* ------------------------------------------- Tarjeta de descarga */
QLabel#DownloadCardTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {p.text_primary};
}}

QLabel#DownloadMeta {{
    font-size: 12px;
    color: {p.text_tertiary};
}}

QLabel#TelemetryLabel {{
    font-size: 12px;
    color: {p.text_secondary};
}}

QLabel#SpeedLabel {{
    font-size: 13px;
    font-weight: 800;
    color: {p.accent_text};
}}

QLabel#CardErrorLabel {{
    font-size: 11px;
    color: {p.danger};
}}

/* -------------------------------------------------- Estados vacíos */
QLabel#EmptyStateTitle {{
    font-size: 17px;
    font-weight: 700;
    color: {p.text_primary};
}}

QLabel#EmptyStateHint {{
    font-size: 13px;
    color: {p.text_tertiary};
}}

/* ------------------------------------------------------------ Varios */
QLabel#SidebarFooter {{
    font-size: 10px;
    color: {p.text_tertiary};
    padding-left: 8px;
}}
"""


DARK_STYLE = build_qss(DARK_PALETTE)
