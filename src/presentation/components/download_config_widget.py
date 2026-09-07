"""Componente de configuración de descarga (carpeta de destino, nombre de archivo, recorte y preset).

Permite al usuario:
- Ver y seleccionar la carpeta de destino mediante el explorador nativo.
- Ver y editar el nombre del archivo final antes de descargar.
- Opcionalmente recortar un fragmento (desde / hasta).
- Seleccionar presets avanzados de conversión de audio con metadatos ID3.
- Valida y sanitiza las rutas según las políticas de nombres de Windows.
"""

import os
import re
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.value_objects.audio_preset import AudioPreset
from src.domain.value_objects.time_range import TimeRange


class DownloadConfigWidget(QFrame):
    """Contenedor de configuración: ruta, nombre de archivo, recorte de tiempo y opciones de audio."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DownloadConfigBox")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        # -------------------------------- 1. Carpeta de destino
        dest_box = QVBoxLayout()
        dest_box.setSpacing(5)

        lbl_dest = QLabel("Carpeta de descarga")
        lbl_dest.setObjectName("FieldLabel")

        dest_row = QHBoxLayout()
        dest_row.setSpacing(10)

        default_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        self.txt_dest = QLineEdit(default_downloads)
        self.txt_dest.setObjectName("PathInput")
        self.txt_dest.setFixedHeight(36)

        self.btn_browse = QPushButton("Examinar...")
        self.btn_browse.setObjectName("SecondaryButton")
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setFixedHeight(36)
        self.btn_browse.clicked.connect(self._on_browse_clicked)

        dest_row.addWidget(self.txt_dest, stretch=1)
        dest_row.addWidget(self.btn_browse)

        dest_box.addWidget(lbl_dest)
        dest_box.addLayout(dest_row)
        layout.addLayout(dest_box)

        # -------------------------------- 2. Nombre del archivo
        file_box = QVBoxLayout()
        file_box.setSpacing(5)

        lbl_filename = QLabel("Nombre del archivo")
        lbl_filename.setObjectName("FieldLabel")

        self.txt_filename = QLineEdit("")
        self.txt_filename.setObjectName("FilenameInput")
        self.txt_filename.setPlaceholderText("Nombre del archivo final...")
        self.txt_filename.setClearButtonEnabled(True)
        self.txt_filename.setFixedHeight(36)

        file_box.addWidget(lbl_filename)
        file_box.addWidget(self.txt_filename)
        layout.addLayout(file_box)

        # -------------------------------- 3. Recorte de fragmento (Tiempo)
        trim_box = QVBoxLayout()
        trim_box.setSpacing(5)

        self.chk_trim = QCheckBox("Recortar fragmento (Opcional)")
        self.chk_trim.setChecked(False)
        self.chk_trim.toggled.connect(self._on_trim_toggled)

        self.trim_controls = QWidget()
        trim_layout = QHBoxLayout(self.trim_controls)
        trim_layout.setContentsMargins(0, 0, 0, 0)
        trim_layout.setSpacing(10)

        lbl_start = QLabel("Desde:")
        self.txt_start = QLineEdit("")
        self.txt_start.setPlaceholderText("00:00")
        self.txt_start.setMaximumWidth(90)
        self.txt_start.setFixedHeight(36)

        lbl_end = QLabel("Hasta:")
        self.txt_end = QLineEdit("")
        self.txt_end.setPlaceholderText("02:30")
        self.txt_end.setMaximumWidth(90)
        self.txt_end.setFixedHeight(36)

        trim_layout.addWidget(lbl_start)
        trim_layout.addWidget(self.txt_start)
        trim_layout.addWidget(lbl_end)
        trim_layout.addWidget(self.txt_end)
        trim_layout.addStretch()

        self.trim_controls.hide()
        trim_box.addWidget(self.chk_trim)
        trim_box.addWidget(self.trim_controls)
        layout.addLayout(trim_box)

        # -------------------------------- 4. Opciones de Audio Profesional
        self.audio_options_box = QWidget()
        audio_layout = QVBoxLayout(self.audio_options_box)
        audio_layout.setContentsMargins(0, 0, 0, 0)
        audio_layout.setSpacing(6)

        lbl_preset = QLabel("Preset de audio profesional:")
        lbl_preset.setObjectName("FieldLabel")
        self.combo_audio_preset = QComboBox()
        self.combo_audio_preset.setFixedHeight(36)
        for preset in AudioPreset:
            self.combo_audio_preset.addItem(preset.display_name, preset.value)

        self.chk_embed_thumbnail = QCheckBox("Incrustar carátula y metadatos ID3")
        self.chk_embed_thumbnail.setChecked(True)

        audio_layout.addWidget(lbl_preset)
        audio_layout.addWidget(self.combo_audio_preset)
        audio_layout.addWidget(self.chk_embed_thumbnail)

        self.audio_options_box.hide()
        layout.addWidget(self.audio_options_box)

    def _on_trim_toggled(self, checked: bool) -> None:
        self.trim_controls.setVisible(checked)

    def set_audio_mode(self, is_audio: bool) -> None:
        """Muestra u oculta los controles específicos para descarga de audio."""
        self.audio_options_box.setVisible(is_audio)

    def _on_browse_clicked(self) -> None:
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Carpeta de Destino",
            self.txt_dest.text().strip() or os.path.expanduser("~"),
        )
        if selected_dir:
            self.txt_dest.setText(os.path.normpath(selected_dir))

    def set_suggested_title(self, raw_title: str) -> None:
        """Establece el nombre sugerido a partir del título del medio."""
        cleaned = self.sanitize_filename(raw_title)
        self.txt_filename.setText(cleaned)

    def get_destination_directory(self) -> str:
        return self.txt_dest.text().strip()

    def set_destination_directory(self, path: str) -> None:
        """Actualiza la ruta de la carpeta de destino."""
        if path and path.strip():
            self.txt_dest.setText(path.strip())

    def get_sanitized_filename(self, fallback: str = "descarga") -> str:
        custom_name = self.txt_filename.text().strip()
        if not custom_name:
            custom_name = fallback
        return self.sanitize_filename(custom_name)

    def get_time_range(self) -> Optional[TimeRange]:
        """Retorna el TimeRange si el recorte está activo y tiene valores válidos."""
        if not self.chk_trim.isChecked():
            return None
        start_raw = self.txt_start.text().strip()
        end_raw = self.txt_end.text().strip()
        if not start_raw and not end_raw:
            return None
        try:
            return TimeRange.from_strings(start_raw, end_raw if end_raw else None)
        except Exception:
            return None

    def get_audio_preset(self) -> Optional[AudioPreset]:
        """Retorna el preset de audio seleccionado si la sección está visible."""
        if self.audio_options_box.isHidden():
            return None
        val = self.combo_audio_preset.currentData()
        if val:
            return AudioPreset.from_string(str(val))
        return AudioPreset.MP3_320K

    def get_embed_thumbnail(self) -> bool:
        return self.chk_embed_thumbnail.isChecked()

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitiza el nombre de archivo eliminando caracteres prohibidos en Windows."""
        if not name:
            return "descarga"
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        cleaned = cleaned.strip().rstrip(".")
        if not cleaned:
            return "descarga"
        return cleaned[:180]

