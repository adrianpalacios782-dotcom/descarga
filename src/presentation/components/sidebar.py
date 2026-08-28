from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import src as app_pkg
from src.presentation.components.app_icons import NAV_ICONS
from src.presentation.styles.styles import DARK_PALETTE

# Grupos de navegación: PRINCIPAL / BIBLIOTECA / SISTEMA.
# Los ids de botón (0..5) son el índice del stacked y NO deben cambiar.
_NAV_GROUPS = [
    ("PRINCIPAL", [("Inicio", 0), ("Descargas", 1)]),
    ("BIBLIOTECA", [("Historial", 2), ("Favoritos", 3)]),
    ("SISTEMA", [("Configuración", 4), ("Acerca de", 5)]),
]

SIDEBAR_WIDTH = 220


class SidebarWidget(QFrame):
    """Sidebar estilo Studio: logo con acento, navegación con badges de
    conteo y tarjeta de pie con versión y perfil."""

    nav_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarFrame")
        self.setFixedWidth(SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 16)
        layout.setSpacing(2)

        # -------------------------------------------------- Logo de marca
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(8, 0, 0, 0)
        logo_row.setSpacing(8)
        logo_mark = QLabel("◆")
        logo_mark.setObjectName("LogoMark")
        logo_text = QLabel("osvaldoDownloader")
        logo_text.setObjectName("SidebarTitle")
        logo_row.addWidget(logo_mark)
        logo_row.addWidget(logo_text)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(10)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._badges: dict[int, QLabel] = {}

        for group_index, (group_title, items) in enumerate(_NAV_GROUPS):
            if group_index > 0:
                divider = QFrame()
                divider.setObjectName("SidebarDivider")
                divider.setFrameShape(QFrame.Shape.NoFrame)
                divider.setFixedHeight(1)
                layout.addSpacing(8)
                layout.addWidget(divider)
                layout.addSpacing(2)

            group_label = QLabel(group_title)
            group_label.setObjectName("SidebarGroupLabel")
            layout.addWidget(group_label)

            for text, index in items:
                layout.addWidget(self._make_nav_row(text, index))

        layout.addStretch()

        # ------------------------------------- Tarjeta de pie (perfil)
        profile_card = QFrame()
        profile_card.setObjectName("SidebarProfileCard")
        card_layout = QHBoxLayout(profile_card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(9)

        dot = QLabel()
        dot.setObjectName("ProfileDot")
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        name_lbl = QLabel("Perfil local")
        name_lbl.setObjectName("ProfileName")
        version_lbl = QLabel(f"v{app_pkg.__version__} · Studio")
        version_lbl.setObjectName("ProfileMeta")
        text_col.addWidget(name_lbl)
        text_col.addWidget(version_lbl)

        card_layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        card_layout.addLayout(text_col, stretch=1)
        layout.addWidget(profile_card)

        # Estado activo inicial + iconos que reaccionan al cambio de sección.
        first = self.button_group.button(0)
        if first is not None:
            first.setChecked(True)
        self._refresh_icon_colors(0)
        self.button_group.idToggled.connect(self._on_toggled)
        self.button_group.idClicked.connect(self.nav_changed.emit)

    def _make_nav_row(self, text: str, index: int) -> QWidget:
        """Fila de navegación: botón estirable + badge de conteo a la derecha."""
        row = QWidget()
        row.setObjectName("NavRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setIcon(NAV_ICONS[index](DARK_PALETTE.text_secondary))
        btn.setIconSize(QSize(19, 19))
        btn.setCursor(self.cursor())
        self.button_group.addButton(btn, index)
        row_layout.addWidget(btn, stretch=1)

        badge = QLabel("")
        badge.setObjectName("NavBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.hide()
        self._badges[index] = badge
        row_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        return row

    def set_badge(self, nav_index: int, count: int) -> None:
        """Actualiza el contador de una sección; se oculta cuando es cero."""
        badge = self._badges.get(nav_index)
        if badge is None:
            return
        if count > 0:
            badge.setText(str(count))
            badge.show()
        else:
            badge.hide()

    def _on_toggled(self, index: int, checked: bool) -> None:
        if checked:
            self._refresh_icon_colors(index)

    def _refresh_icon_colors(self, active_index: int) -> None:
        """El icono de la sección activa toma el acento; el resto, gris."""
        for index in range(6):
            button = self.button_group.button(index)
            if button is None:
                continue
            color = (
                DARK_PALETTE.accent_text
                if index == active_index
                else DARK_PALETTE.text_secondary
            )
            button.setIcon(NAV_ICONS[index](color))
