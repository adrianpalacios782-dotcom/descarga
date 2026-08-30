"""Componente de configuración de descarga (carpeta de destino y nombre de archivo).

Permite al usuario:
- Ver y seleccionar la carpeta de destino mediante el explorador nativo.
- Ver y editar el nombre del archivo final antes de descargar.
- Valida y sanitiza las rutas según las políticas de nombres de Windows.
"""

import os
import re
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DownloadConfigWidget(QFrame):
    """Contenedor de configuración: ruta de descarga y nombre de archivo editable."""

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

        self.btn_browse = QPushButton("Examinar...")
        self.btn_browse.setObjectName("SecondaryButton")
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
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

        file_box.addWidget(lbl_filename)
        file_box.addWidget(self.txt_filename)
        layout.addLayout(file_box)

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
