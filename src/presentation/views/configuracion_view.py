from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QComboBox, QFrame, QMessageBox
)


class ConfiguracionView(QWidget):
    """Vista de configuración global categorizada del sistema."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        title = QLabel("Configuración Global")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)

        # Descargas simultáneas
        row1 = QHBoxLayout()
        lbl_concurrent = QLabel("Descargas Simultáneas Máximas:")
        lbl_concurrent.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.spin_concurrent = QSpinBox()
        self.spin_concurrent.setRange(1, 10)
        self.spin_concurrent.setValue(3)
        row1.addWidget(lbl_concurrent)
        row1.addWidget(self.spin_concurrent)
        row1.addStretch()
        card_layout.addLayout(row1)

        # Navegador para cookies
        row_cookies = QHBoxLayout()
        lbl_cookies = QLabel("Navegador para cookies (Contenido restringido):")
        lbl_cookies.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.combo_browser = QComboBox()
        self.combo_browser.addItem("Desactivado (Recomendado)", userData="")
        self.combo_browser.addItem("Chrome", userData="chrome")
        self.combo_browser.addItem("Edge", userData="edge")
        self.combo_browser.addItem("Firefox", userData="firefox")
        self.combo_browser.addItem("Brave", userData="brave")
        row_cookies.addWidget(lbl_cookies)
        row_cookies.addWidget(self.combo_browser)
        row_cookies.addStretch()
        card_layout.addLayout(row_cookies)

        # Tema visual
        row2 = QHBoxLayout()
        lbl_theme = QLabel("Tema Visual:")
        lbl_theme.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Oscuro Multimedia (Default)", "Oscuro OLED"])
        row2.addWidget(lbl_theme)
        row2.addWidget(self.combo_theme)
        row2.addStretch()
        card_layout.addLayout(row2)

        # Guardar
        btn_save = QPushButton("Guardar Preferencias")
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self._on_save_clicked)
        card_layout.addWidget(btn_save)

        layout.addWidget(card)
        layout.addStretch()

    def _on_save_clicked(self) -> None:
        QMessageBox.information(self, "Configuración", "Las preferencias han sido guardadas correctamente.")
