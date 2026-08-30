import os
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.domain.ports.settings_repository import ISettingsRepository


class ConfiguracionView(QWidget):
    """Vista de configuración global agrupada por paneles con persistencia real."""

    update_check_requested = Signal()
    animations_enabled_changed = Signal(bool)
    settings_saved = Signal(dict)

    def __init__(
        self,
        settings_repo: Optional[ISettingsRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.settings_repo = settings_repo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Configuración Global")
        title.setObjectName("ViewTitle")
        layout.addWidget(title)

        # ------------------------------------------------------ DESCARGAS
        self.txt_default_dir = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads"))
        self.btn_browse_dir = QPushButton("Examinar...")
        self.btn_browse_dir.setObjectName("SecondaryButton")
        self.btn_browse_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_dir.clicked.connect(self._on_browse_dir_clicked)

        dir_widget = QWidget()
        dir_layout = QHBoxLayout(dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(8)
        dir_layout.addWidget(self.txt_default_dir, stretch=1)
        dir_layout.addWidget(self.btn_browse_dir)

        self.chk_ask_destination = QCheckBox("Preguntar dónde guardar cada descarga")
        self.chk_ask_destination.setChecked(False)

        self.chk_tray_notifications = QCheckBox("Mostrar notificaciones de Windows al completar descargas")
        self.chk_tray_notifications.setChecked(True)

        layout.addWidget(self._build_section_card("DESCARGAS", [
            self._row("Carpeta predeterminada:", dir_widget),
            self.chk_ask_destination,
            self.chk_tray_notifications,
            self._row("Descargas simultáneas máximas:", self._spin_concurrent()),
            self._hint("Número máximo de descargas ejecutándose a la vez."),
        ]))

        # ----------------------------------------------------- APARIENCIA
        self.chk_animations = QCheckBox("Animaciones de la interfaz")
        self.chk_animations.setChecked(True)
        self.chk_animations.toggled.connect(self.animations_enabled_changed.emit)

        self.chk_minimize_to_tray = QCheckBox("Minimizar a la bandeja del sistema al cerrar la ventana")
        self.chk_minimize_to_tray.setChecked(False)

        layout.addWidget(self._build_section_card("APARIENCIA", [
            self._row("Tema Visual:", self._combo_theme()),
            self._hint("Tema oscuro optimizado para contenido multimedia."),
            self.chk_animations,
            self.chk_minimize_to_tray,
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
        updates_layout = self.updates_card.layout()
        if isinstance(updates_layout, QVBoxLayout):
            updates_layout.addLayout(row_updates)
        layout.addWidget(self.updates_card)

        # ------------------------------------------------------- AVANZADO
        layout.addWidget(self._build_section_card("AVANZADO", [
            self._row("Navegador para cookies (Contenido restringido):", self._combo_browser()),
            self._hint("Usa las cookies de tu navegador solo si el contenido requiere inicio de sesión."),
        ]))

        btn_save = QPushButton("Guardar Preferencias")
        btn_save.setObjectName("SecondaryButton")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._on_save_clicked)
        layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

        if self.settings_repo is not None:
            self.load_settings()

    # ----------------------------------------------------------------- UI
    @staticmethod
    def _section_header(text: str) -> QLabel:
        header = QLabel(text)
        header.setObjectName("SectionHeader")
        return header

    def _build_section_card(self, section: str, rows: list[Any]) -> QFrame:
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
    def _row(label_text: str, widget: QWidget) -> QHBoxLayout:
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
        self.spin_concurrent.setValue(2)
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

    # -------------------------------------------------------- Persistencia
    def set_settings_repository(self, repo: ISettingsRepository) -> None:
        """Asigna el repositorio de configuraciones y carga los valores actuales."""
        self.settings_repo = repo
        self.load_settings()

    def load_settings(self) -> None:
        """Carga las configuraciones persistidas en los controles visuales."""
        if self.settings_repo is None:
            return
        saved = self.settings_repo.get_all()

        if "default_download_dir" in saved:
            self.txt_default_dir.setText(str(saved["default_download_dir"]))
        if "ask_destination" in saved:
            self.chk_ask_destination.setChecked(bool(saved["ask_destination"]))
        if "max_concurrent_downloads" in saved:
            try:
                self.spin_concurrent.setValue(int(saved["max_concurrent_downloads"]))
            except (ValueError, TypeError):
                pass
        if "theme" in saved:
            idx = self.combo_theme.findText(str(saved["theme"]))
            if idx >= 0:
                self.combo_theme.setCurrentIndex(idx)
        if "animations_enabled" in saved:
            self.chk_animations.setChecked(bool(saved["animations_enabled"]))
        if "minimize_to_tray" in saved:
            self.chk_minimize_to_tray.setChecked(bool(saved["minimize_to_tray"]))
        if "tray_notifications" in saved:
            self.chk_tray_notifications.setChecked(bool(saved["tray_notifications"]))
        if "cookies_browser" in saved:
            browser_key = str(saved["cookies_browser"])
            idx = self.combo_browser.findData(browser_key)
            if idx >= 0:
                self.combo_browser.setCurrentIndex(idx)

    # ------------------------------------------------------------ Acciones
    def _on_browse_dir_clicked(self) -> None:
        current_dir = self.txt_default_dir.text().strip() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Carpeta Predeterminada de Descargas",
            current_dir,
        )
        if folder:
            self.txt_default_dir.setText(os.path.normpath(folder))

    def _on_save_clicked(self) -> None:
        browser_val = self.combo_browser.currentData()
        settings = {
            "default_download_dir": self.txt_default_dir.text().strip(),
            "ask_destination": self.chk_ask_destination.isChecked(),
            "tray_notifications": self.chk_tray_notifications.isChecked(),
            "max_concurrent_downloads": self.spin_concurrent.value(),
            "theme": self.combo_theme.currentText(),
            "animations_enabled": self.chk_animations.isChecked(),
            "minimize_to_tray": self.chk_minimize_to_tray.isChecked(),
            "cookies_browser": str(browser_val) if browser_val is not None else "",
        }

        if self.settings_repo is not None:
            self.settings_repo.set(
                "default_download_dir", settings["default_download_dir"], "str", "downloads"
            )
            self.settings_repo.set(
                "ask_destination", settings["ask_destination"], "bool", "downloads"
            )
            self.settings_repo.set(
                "tray_notifications", settings["tray_notifications"], "bool", "downloads"
            )
            self.settings_repo.set(
                "max_concurrent_downloads", settings["max_concurrent_downloads"], "int", "downloads"
            )
            self.settings_repo.set(
                "theme", settings["theme"], "str", "appearance"
            )
            self.settings_repo.set(
                "animations_enabled", settings["animations_enabled"], "bool", "appearance"
            )
            self.settings_repo.set(
                "minimize_to_tray", settings["minimize_to_tray"], "bool", "appearance"
            )
            self.settings_repo.set(
                "cookies_browser", settings["cookies_browser"], "str", "advanced"
            )

        self.settings_saved.emit(settings)
        QMessageBox.information(
            self, "Configuración", "Las preferencias han sido guardadas correctamente."
        )
