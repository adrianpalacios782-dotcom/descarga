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
    bg_window="#F8FAFC",
    bg_sidebar="#F1F5F9",
    bg_titlebar="#F1F5F9",
    surface="#FFFFFF",
    surface_hover="#F1F5F9",
    surface_active="#E2E8F0",
    surface_sunken="#F8FAFC",
    border="rgba(0, 0, 0, 0.08)",
    border_strong="rgba(0, 0, 0, 0.16)",
    border_focus="#4F46E5",
    text_primary="#0F172A",
    text_secondary="#475569",
    text_tertiary="#94A3B8",
    text_on_accent="#FFFFFF",
    accent="#4F46E5",
    accent_hover="#6366F1",
    accent_pressed="#4338CA",
    accent_dim="rgba(79, 70, 229, 0.12)",
    accent_text="#4F46E5",
    danger="#EF4444",
    warning="#F59E0B",
    close_hover_bg="#e81123",
)


OLED_PALETTE = Palette(
    bg_window="#000000",
    bg_sidebar="#000000",
    bg_titlebar="#000000",
    surface="#0B0B0B",
    surface_hover="#141414",
    surface_active="#1F1F1F",
    surface_sunken="#050505",
    border="rgba(255, 255, 255, 0.12)",
    border_strong="rgba(255, 255, 255, 0.22)",
    border_focus="#6366F1",
    text_primary="#FFFFFF",
    text_secondary="#A1A1AA",
    text_tertiary="#71717A",
    text_on_accent="#FFFFFF",
    accent="#6366F1",
    accent_hover="#818CF8",
    accent_pressed="#4F46E5",
    accent_dim="rgba(99, 102, 241, 0.16)",
    accent_text="#A5B4FC",
    danger="#EF4444",
    warning="#F59E0B",
    close_hover_bg="#e81123",
)


THEME_PALETTES: dict[str, Palette] = {
    "Oscuro Multimedia (Default)": DARK_PALETTE,
    "Oscuro OLED": OLED_PALETTE,
    "Claro Moderno": LIGHT_PALETTE,
    "Claro": LIGHT_PALETTE,
    "Oscuro": DARK_PALETTE,
}

ThemeTokens = Palette

_CURRENT_THEME: str = "Oscuro Multimedia (Default)"
_CURRENT_PALETTE: Palette = DARK_PALETTE


def set_current_theme(theme_name: str) -> None:
    """Actualiza el tema actual y sincroniza la paleta activa."""
    global _CURRENT_THEME, _CURRENT_PALETTE
    _CURRENT_THEME = theme_name
    _CURRENT_PALETTE = get_theme_palette(theme_name)


def get_current_theme() -> str:
    """Retorna el nombre del tema activo."""
    return _CURRENT_THEME


def get_current_palette() -> Palette:
    """Retorna la paleta de tokens activa del sistema."""
    return _CURRENT_PALETTE


def get_theme_palette(theme_name: str) -> Palette:
    return THEME_PALETTES.get(theme_name, DARK_PALETTE)


def get_theme_qss(theme_name: str) -> str:
    set_current_theme(theme_name)
    palette = get_theme_palette(theme_name)
    return build_qss(palette)


def build_qss(p: Palette) -> str:
    """Genera la hoja de estilos completa a partir de una paleta y los tokens."""
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

/* ------------------------------------------------ Menús contextuales */
QMenu {{
    background-color: {p.surface};
    color: {p.text_primary};
    border: 1px solid {p.border_strong};
    border-radius: 8px;
    padding: 6px 4px;
}}

QMenu::item {{
    background-color: transparent;
    color: {p.text_primary};
    padding: 8px 24px 8px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
}}

QMenu::item:selected {{
    background-color: {p.surface_active};
    color: {p.accent_text};
}}

QMenu::item:disabled {{
    color: {p.text_tertiary};
    background-color: transparent;
}}

QMenu::separator {{
    height: 1px;
    background-color: {p.border};
    margin: 4px 8px;
}}


/* ------------------------------------------------ Barra de título */
QWidget#TitleBar {{
    background-color: {p.bg_titlebar};
    border-bottom: 1px solid {p.border};
}}

QWidget#TitleBarDrag {{
    background-color: transparent;
}}

QLabel#TitleBrandIcon {{
    background-color: transparent;
    border-radius: 4px;
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
    font-size: {FONT_SIZE['micro']}px;
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
    padding: 6px 14px;
    min-height: 24px;
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
    padding: 10px 16px;
    min-height: 24px;
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
    padding: 4px 34px 4px 14px;
    min-height: 26px;
    color: {p.text_primary};
    font-size: 13px;
    font-weight: 500;
}}

QComboBox:hover {{
    border-color: {p.border_strong};
}}

QComboBox:focus {{
    border-color: {p.border_focus};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {p.text_tertiary};
    margin-right: 12px;
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

QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 4px 10px;
}}

QCheckBox {{
    spacing: 10px;
    color: {p.text_secondary};
    font-size: 13px;
    min-height: 24px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {p.border_strong};
    background-color: {p.surface_sunken};
}}

QCheckBox::indicator:hover {{
    border-color: {p.accent};
}}

QCheckBox::indicator:checked {{
    background-color: {p.accent};
    border-color: {p.accent};
}}

QSpinBox {{
    background-color: {p.surface_sunken};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 4px 12px;
    min-height: 26px;
    color: {p.text_primary};
    font-size: 13px;
}}

QSpinBox:focus {{
    border: 1px solid {p.border_focus};
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
    spacing: 0px;
}}

QRadioButton#QualityRadio::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 2px solid {p.border_strong};
    background-color: {p.surface_sunken};
}}

QRadioButton#QualityRadio::indicator:hover {{
    border-color: {p.accent_hover};
}}

QRadioButton#QualityRadio::indicator:checked {{
    border: 2px solid {p.accent};
    background-color: {p.accent};
}}

QFrame#FormatTableHeader {{
    background-color: transparent;
    border-bottom: 1px solid {p.border};
    margin-bottom: 2px;
}}

QLabel#TableHeaderCol {{
    color: {p.text_secondary};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
}}

QLabel#FormatColText {{
    color: {p.text_primary};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#TechColText {{
    color: {p.text_secondary};
    font-size: 12px;
}}

QLabel#BadgeRecommended {{
    background-color: rgba(99, 102, 241, 0.2);
    color: #818CF8;
    border: 1px solid rgba(99, 102, 241, 0.45);
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 7px;
    letter-spacing: 0.3px;
}}

QLabel#BadgeHD {{
    background-color: rgba(34, 197, 94, 0.16);
    color: #4ADE80;
    border: 1px solid rgba(34, 197, 94, 0.35);
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
}}

QLabel#BadgeQuality {{
    background-color: rgba(148, 163, 184, 0.14);
    color: {p.text_secondary};
    border: 1px solid {p.border};
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
}}

QFrame#DownloadConfigBox {{
    background-color: {p.surface_sunken};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

QLineEdit#FilenameInput, QLineEdit#PathInput {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 8px 12px;
    color: {p.text_primary};
    font-size: 13px;
}}

QLineEdit#FilenameInput:focus, QLineEdit#PathInput:focus {{
    border-color: {p.border_focus};
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

QFrame#UrlBar[drag_active="true"] {{
    border: 2px dashed {p.accent};
    background-color: {p.surface_active};
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
