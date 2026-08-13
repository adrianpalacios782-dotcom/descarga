from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel, QButtonGroup


class SidebarWidget(QFrame):
    """Barra lateral de navegación principal con las 6 secciones limpias sin emojis."""
    nav_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarFrame")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(10)

        title_label = QLabel("osvaldoDownloaderPro")
        title_label.setStyleSheet("font-size: 15px; font-weight: 800; color: #1db954; letter-spacing: 0.5px; padding-bottom: 16px;")
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
            if index == 0:
                btn.setChecked(True)
            self.button_group.addButton(btn, index)
            layout.addWidget(btn)

        layout.addStretch()

        self.button_group.idClicked.connect(self._on_id_clicked)

    def _on_id_clicked(self, index: int) -> None:
        self.nav_changed.emit(index)
