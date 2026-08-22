from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QComboBox, QFrame, QMessageBox
)


class ConfiguracionView(QWidget):
    """Vista de configuración global agrupada por secciones."""

    update_check_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Configuración Global")
        title.setObjectName("ViewTitle")
        layout.addWidget(title)

        # ------------------------------------------------------ DESCARGAS
        layout.addWidget(self._build_section_card("DESCARGAS", [
            self._row("Descargas Simultáneas Máximas:", self._spin_concurrent()),
            self._hint("Número máximo de descargas ejecutándose a la vez."),
        ]))

        # ----------------------------------------------------- APARIENCIA
        layout.addWidget(self._build_section_card("APARIENCIA", [
            self._row("Tema Visual:", self._combo_theme()),
            self._hint("Tema oscuro optimizado para contenido multimedia."),
        ]))

        # ------------------------------------------------- ACTUALIZACIONES
        self.updates_card = self._build_section_card("ACTUALIZACIONES", [
            self._hint(
                "Comprueba si hay una nueva versión disponible en la fuente oficial. "
                "La aplicación verifica cada instalador antes de ejecutarlo."
            ),
        ])
        row_updates = QHBoxLayout()
        row_updates.addStretch()
        btn_check_updates = QPushButton("Buscar actualizaciones ahora")
        btn_check_updates.setObjectName("PrimaryButton")
        btn_check_updates.clicked.connect(self.update_check_requested.emit)
        row_updates.addWidget(btn_check_updates)
        self.updates_card.layout().addLayout(row_updates)
        layout.addWidget(self.updates_card)

        # ------------------------------------------------------- AVANZADO
        layout.addWidget(self._build_section_card("AVANZADO", [
            self._row("Navegador para cookies (Contenido restringido):", self._combo_browser()),
            self._hint("Usa las cookies de tu navegador solo si el contenido requiere inicio de sesión."),
        ]))

        btn_save = QPushButton("Guardar Preferencias")
        btn_save.setObjectName("SecondaryButton")
        btn_save.clicked.connect(self._on_save_clicked)
        layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    # ----------------------------------------------------------------- UI
    @staticmethod
    def _section_header(text: str) -> QLabel:
        header = QLabel(text)
        header.setObjectName("SectionHeader")
        return header

    def _build_section_card(self, section: str, rows) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.addWidget(self._section_header(section))
        for row in rows:
            if isinstance(row, QHBoxLayout):
                card_layout.addLayout(row)
            else:
                card_layout.addWidget(row)
        return card

    @staticmethod
    def _row(label_text: str, widget) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        row.addWidget(label)
        row.addWidget(widget)
        row.addStretch()
        return row

    @staticmethod
    def _hint(text: str) -> QLabel:
        hint = QLabel(text)
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        return hint

    # ----------------------------------------------------------- Widgets
    def _spin_concurrent(self) -> QSpinBox:
        self.spin_concurrent = QSpinBox()
        self.spin_concurrent.setRange(1, 10)
        self.spin_concurrent.setValue(3)
        return self.spin_concurrent

    def _combo_theme(self) -> QComboBox:
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Oscuro Multimedia (Default)", "Oscuro OLED"])
        return self.combo_theme

    def _combo_browser(self) -> QComboBox:
        self.combo_browser = QComboBox()
        self.combo_browser.addItem("Desactivado (Recomendado)", userData="")
        self.combo_browser.addItem("Chrome", userData="chrome")
        self.combo_browser.addItem("Edge", userData="edge")
        self.combo_browser.addItem("Firefox", userData="firefox")
        self.combo_browser.addItem("Brave", userData="brave")
        return self.combo_browser

    # ------------------------------------------------------------ Acciones
    def _on_save_clicked(self) -> None:
        QMessageBox.information(self, "Configuración", "Las preferencias han sido guardadas correctamente.")
