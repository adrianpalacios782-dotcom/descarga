from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
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


class SidebarWidget(QFrame):
    """Barra lateral minimalista: indicador lateral sutil + iconos dinámicos."""

    nav_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarFrame")
        self.setFixedWidth(216)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 20)
        layout.setSpacing(2)

        title_label = QLabel("osvaldoDownloaderPro")
        title_label.setObjectName("SidebarTitle")
        layout.addWidget(title_label)
        layout.addSpacing(6)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

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
                layout.addWidget(self._make_nav_button(text, index))

        layout.addStretch()

        footer = QLabel(f"Versión {app_pkg.__version__}")
        footer.setObjectName("SidebarFooter")
        layout.addWidget(footer)

        # Estado activo inicial + iconos que reaccionan al cambio de sección.
        first = self.button_group.button(0)
        if first is not None:
            first.setChecked(True)
        self._refresh_icon_colors(0)
        self.button_group.idToggled.connect(self._on_toggled)
        self.button_group.idClicked.connect(self.nav_changed.emit)

    def _make_nav_button(self, text: str, index: int) -> QPushButton:
        btn = QPushButton(" " + text)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setIcon(NAV_ICONS[index](DARK_PALETTE.text_secondary))
        btn.setIconSize(QSize(19, 19))
        btn.setCursor(self.cursor())
        self.button_group.addButton(btn, index)
        return btn

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
