from typing import List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox
)

from src.domain.entities.download_task import DownloadTask


class HistorialView(QWidget):
    """Vista para consultar y gestionar el biblioteca e historial de descargas."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Historial de Descargas")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        layout.addWidget(title)

        # Filtros
        filter_box = QHBoxLayout()
        filter_box.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por título...")
        
        self.combo_platform = QComboBox()
        self.combo_platform.addItems(["Todas las plataformas", "YouTube", "TikTok", "Instagram", "Facebook"])

        filter_box.addWidget(self.search_input, stretch=2)
        filter_box.addWidget(self.combo_platform, stretch=1)
        layout.addLayout(filter_box)

        # Tabla de Historial
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Título", "Plataforma", "Formato", "Estado", "Ruta Destino"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table)

    def load_history(self, tasks: List[DownloadTask]) -> None:
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self.table.setItem(row, 0, QTableWidgetItem(task.media.title))
            self.table.setItem(row, 1, QTableWidgetItem(task.media.platform))
            self.table.setItem(row, 2, QTableWidgetItem(task.selected_format.resolution or task.selected_format.extension.upper()))
            self.table.setItem(row, 3, QTableWidgetItem(task.status.value))
            self.table.setItem(row, 4, QTableWidgetItem(task.destination_path))
