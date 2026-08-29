"""Barra de título personalizada estilo minimalista.

Ventana frameless con controles propios (minimizar / maximizar / cerrar).
El arrastre, Aero Snap y el doble clic para maximizar se delegan a Windows
mediante WM_NCHITTEST en MainWindow (HTCAPTION sobre esta zona), por lo que
no se reimplementa lógica frágil de movimiento manual.
"""

import os
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizeGrip, QWidget

import src as app_pkg
from src.presentation.components.app_icons import window_control_icons
from src.presentation.styles.styles import DARK_PALETTE


class TitleBar(QWidget):
    """Barra superior con marca discreta y controles circulares de ventana."""

    minimize_requested = Signal()
    maximize_toggle_requested = Signal()
    close_requested = Signal()

    HEIGHT = 46

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(self.HEIGHT)

        icons = window_control_icons()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(8)

        # Icono de la marca en la barra de título
        self.brand_icon = QLabel()
        self.brand_icon.setObjectName("TitleBrandIcon")
        self.brand_icon.setFixedSize(22, 22)
        self.brand_icon.setScaledContents(True)
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "icon_256.png")
        if not os.path.exists(icon_path):
            base = getattr(sys, "_MEIPASS", "")
            icon_path = os.path.join(base, "assets", "icon_256.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(sys.executable), "assets", "icon_256.png")
        if os.path.exists(icon_path):
            self.brand_icon.setPixmap(QPixmap(icon_path))
            layout.addWidget(self.brand_icon)

        self.brand = QLabel("osvaldoDownloaderPro")
        self.brand.setObjectName("TitleBrand")
        layout.addWidget(self.brand)
        layout.addStretch()

        self.btn_minimize = QPushButton()
        self.btn_minimize.setObjectName("WindowButton")
        self.btn_minimize.setIcon(icons["minimize"])
        self.btn_minimize.setFixedSize(28, 28)
        self.btn_minimize.setToolTip("Minimizar")
        self.btn_minimize.clicked.connect(self.minimize_requested.emit)

        self.btn_maximize = QPushButton()
        self.btn_maximize.setObjectName("WindowButton")
        self.btn_maximize.setIcon(icons["maximize"])
        self.btn_maximize.setFixedSize(28, 28)
        self.btn_maximize.setToolTip("Maximizar")
        self.btn_maximize.clicked.connect(self.maximize_toggle_requested.emit)

        self.btn_close = QPushButton()
        self.btn_close.setObjectName("WindowButton")
        self.btn_close.setProperty("close", True)
        self.btn_close.setIcon(icons["close"])
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setToolTip("Cerrar")
        self.btn_close.clicked.connect(self.close_requested.emit)

        for button in (
            self.btn_minimize,
            self.btn_maximize,
            self.btn_close,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(button)

    def refresh_window_state_icon(self, maximized: bool) -> None:
        icons = window_control_icons()
        self.btn_maximize.setIcon(icons["restore"] if maximized else icons["maximize"])
        self.btn_maximize.setToolTip(
            "Restaurar" if maximized else "Maximizar"
        )

    def is_drag_zone(self, pos) -> bool:
        """True si el punto pertenece a la zona arrastrable (excluye botones)."""
        for button in (self.btn_minimize, self.btn_maximize, self.btn_close):
            if button.geometry().contains(pos):
                return False
        return True
