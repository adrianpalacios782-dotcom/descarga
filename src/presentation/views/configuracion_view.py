from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QComboBox, QFrame
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
        card_layout.addWidget(btn_save)

        layout.addWidget(card)
        layout.addStretch()
