from PySide6.QtCore import Signal, QSize
from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel, QButtonGroup

from src.presentation.components.app_icons import NAV_ICONS


class SidebarWidget(QFrame):
    """Barra lateral de navegación principal con iconos vectoriales y 6 secciones."""

    nav_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarFrame")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(10)

        title_label = QLabel("osvaldoDownloaderPro")
        title_label.setObjectName("SidebarTitle")
        layout.addWidget(title_label)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        items = [
            ("Inicio", 0),
            ("Descargas", 1),
            ("Historial", 2),
            ("Favoritos", 3),
            ("Configuración", 4),
            ("Acerca de", 5)
        ]

        for text, index in items:
            btn = QPushButton(text)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setIcon(NAV_ICONS[index]("#1db954" if index == 0 else "#b3b3b3"))
            btn.setIconSize(QSize(20, 20))
            if index == 0:
                btn.setChecked(True)
            self.button_group.addButton(btn, index)
            layout.addWidget(btn)

        layout.addStretch()

        self.button_group.idClicked.connect(self._on_id_clicked)

    def _on_id_clicked(self, index: int) -> None:
        self.nav_changed.emit(index)
