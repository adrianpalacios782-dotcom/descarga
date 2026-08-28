"""Sistema de diseño centralizado: paletas como tokens y constructor de QSS.

Tema "Studio Desktop": lienzo #0B0F19 con superficies #111827/#1E293B,
bordes sutiles rgba(255,255,255,0.08) y acento índigo #6366F1 reservado
para acciones importantes (Analizar/Descargar/progreso/selección).
Cualquier paleta que exponga los mismos atributos puede alimentar build_qss().
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
    bg_window="#0B0F19",
    bg_sidebar="#0B0F19",
    bg_titlebar="#0B0F19",
    surface="#111827",
    surface_hover="#151E31",
    surface_active="#1E293B",
    surface_sunken="#0F172A",
    border="rgba(255, 255, 255, 0.08)",
    border_strong="rgba(255, 255, 255, 0.16)",
    border_focus="#6366F1",
    text_primary="#F8FAFC",
    text_secondary="#94A3B8",
    text_tertiary="#64748B",
    text_on_accent="#FFFFFF",
    accent="#6366F1",
    accent_hover="#818CF8",
    accent_pressed="#4F46E5",
    accent_dim="rgba(99, 102, 241, 0.14)",
    accent_text="#A5B4FC",
    danger="#EF4444",
    warning="#F59E0B",
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
    border_focus="#6366F1",
    text_primary="#1a1a1e",
    text_secondary="#5c5c66",
    text_tertiary="#9a9aa2",
    text_on_accent="#ffffff",
    accent="#6366F1",
    accent_hover="#818CF8",
    accent_pressed="#4F46E5",
    accent_dim="rgba(99, 102, 241, 0.12)",
    accent_text="#4F46E5",
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
    color: {p.text_secondary};
    padding: 0px 0px 10px 0px;
}}

QLabel#LogoMark {{
    color: {p.accent};
    font-size: 14px;
    padding-bottom: 10px;
}}

QPushButton#NavButton {{
    background-color: transparent;
    color: {p.text_secondary};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 8px;
    padding: 9px 10px 9px 12px;
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

QWidget#NavRow {{
    background-color: transparent;
}}

QLabel#NavBadge {{
    background-color: {p.accent_dim};
    color: {p.accent_text};
    border: 1px solid {p.border};
    border-radius: 9px;
    min-width: 14px;
    padding: 1px 7px;
    font-size: 10px;
    font-weight: 800;
    qproperty-alignment: AlignCenter;
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
    background-color: {p.accent_dim};
    color: {p.accent_text};
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

/* ------------------------------------------- Filas de formato (Studio) */
/* Filas limpias [icono][título·badge][codec/fps][tamaño][Descargar]:
   cero cuadrículas rígidas y cero skeletons con texto roto. */
QFrame#FormatRow, QFrame#QualityCard {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

QFrame#FormatRow:hover, QFrame#QualityCard:hover {{
    background-color: {p.surface_hover};
    border-color: {p.border_strong};
}}

QFrame#FormatRow[selected="true"], QFrame#QualityCard[selected="true"] {{
    background-color: #172033;
    border: 1px solid {p.accent};
}}

QLabel#FormatRowIcon {{
    font-size: 15px;
    color: {p.accent_text};
    background-color: {p.accent_dim};
    border-radius: 8px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    qproperty-alignment: AlignCenter;
}}

QLabel#QualityTitle {{
    background-color: transparent;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 700;
}}

QRadioButton#QualityRadio {{
    background-color: transparent;
    color: transparent;
    font-size: 1px;
    spacing: 0px;
}}

QRadioButton#QualityRadio::indicator {{
    width: 0px;
    height: 0px;
    border: none;
    background-color: transparent;
}}

QPushButton#FormatRowDownload {{
    background-color: {p.accent};
    color: {p.text_on_accent};
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 800;
}}

QPushButton#FormatRowDownload:hover {{
    background-color: {p.accent_hover};
}}

QPushButton#FormatRowDownload:pressed {{
    background-color: {p.accent_pressed};
}}

/* ------------------------------------- Barra de URL integrada (Studio) */
QFrame#UrlBar {{
    background-color: {p.surface_sunken};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

QFrame#UrlBar[property~="invalid"] {{
    border: 1px solid {p.danger};
}}

QFrame#UrlBar[property~="valid"] {{
    border: 1px solid {p.border_focus};
}}

QLineEdit#UrlInput {{
    background-color: transparent;
    border: none;
    font-size: 14px;
    padding: 11px 4px;
}}

QPushButton#InlineButton {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: {p.text_secondary};
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 700;
}}

QPushButton#InlineButton:hover {{
    background-color: {p.surface_active};
    color: {p.text_primary};
}}

/* ------------------------------------ Badge de duración sobre miniatura */
QFrame#ThumbWrap {{
    background-color: transparent;
    border: none;
}}

QLabel#DurationBadge {{
    background-color: rgba(0, 0, 0, 0.78);
    color: #FFFFFF;
    border-radius: 8px;
    padding: 2px 8px;
    margin: 0px 8px 8px 0px;
    font-size: 11px;
    font-weight: 700;
}}

/* --------------------------------- Indicador limpio de "Analizando..." */
QProgressBar#AnalyzingBar {{
    background-color: {p.surface_active};
    border: none;
    border-radius: 3px;
    min-height: 5px;
    max-height: 5px;
    color: transparent;
}}

QProgressBar#AnalyzingBar::chunk {{
    background-color: {p.accent};
    border-radius: 3px;
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
    color: #94A3B8;
}}

QLabel#QualitySize {{
    font-size: 11px;
    font-weight: 600;
    color: #CBD5E1;
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

QLabel#CardWarningLabel {{
    font-size: 11px;
    font-weight: 600;
    color: {p.warning};
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
QFrame#SidebarProfileCard {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

QLabel#ProfileDot {{
    background-color: {p.accent};
    border-radius: 4px;
    max-width: 8px;
    max-height: 8px;
    min-width: 8px;
    min-height: 8px;
}}

QLabel#ProfileName {{
    font-size: 12px;
    font-weight: 700;
    color: {p.text_primary};
}}

QLabel#ProfileMeta {{
    font-size: 10px;
    color: {p.text_tertiary};
}}

/* ============================================================
   Studio Desktop — Monitor de actividad (sidebar derecho)
   ============================================================ */

QFrame#ActivityPanel {{
    background-color: {p.bg_sidebar};
    border-left: 1px solid {p.border};
}}

QLabel#ActivityHeader {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.4px;
    color: {p.text_tertiary};
}}

QToolButton#CollapseButton {{
    background-color: transparent;
    border: 1px solid {p.border};
    border-radius: 8px;
    color: {p.text_secondary};
    font-size: 14px;
    font-weight: 700;
    padding: 2px 8px;
}}

QToolButton#CollapseButton:hover {{
    background-color: {p.surface_hover};
    color: {p.text_primary};
}}

QLabel#RailTitle {{
    color: {p.text_tertiary};
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
}}

QFrame#ActivityCard {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

QFrame#ActivityCard:hover {{
    border-color: {p.border_strong};
}}

QLabel#ActivityTitle {{
    font-size: 12px;
    font-weight: 700;
    color: {p.text_primary};
}}

QLabel#ActivityStatus {{
    font-size: 10px;
    font-weight: 600;
    color: {p.text_secondary};
}}

QLabel#ActivitySpeed {{
    font-size: 11px;
    font-weight: 800;
    color: {p.accent_text};
}}

QLabel#ActivityPct {{
    font-size: 11px;
    font-weight: 800;
    color: {p.text_primary};
}}

QToolButton#ActivityBtn {{
    background-color: {p.surface_hover};
    border: 1px solid {p.border};
    border-radius: 7px;
    color: {p.text_secondary};
    font-size: 10px;
    padding: 2px 6px;
    font-weight: 700;
}}

QToolButton#ActivityBtn:hover {{
    background-color: {p.surface_active};
    color: {p.text_primary};
}}

QProgressBar#ActivityProgress {{
    background-color: {p.surface_active};
    border: none;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
    color: transparent;
}}

QProgressBar#ActivityProgress::chunk {{
    background-color: {p.accent};
    border-radius: 3px;
}}

QLabel#HistoryRow {{
    font-size: 11px;
    color: {p.text_secondary};
    padding: 2px 0px;
}}

QFrame#MetricsCard {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 14px;
}}

QLabel#MetricValue {{
    font-size: 17px;
    font-weight: 800;
    color: {p.text_primary};
}}

QLabel#MetricLabel {{
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.0px;
    color: {p.text_tertiary};
}}

QLabel#EmptyMonitorLabel {{
    font-size: 11px;
    color: {p.text_tertiary};
}}
"""


DARK_STYLE = build_qss(DARK_PALETTE)
