from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox
)

from src.domain.entities.download_task import DownloadTask
from src.domain.services.content_preview import format_size_bytes
from src.presentation.components.status_labels import humanize_download_state


class HistorialView(QWidget):
    """Vista para consultar el historial de descargas con búsqueda y filtro por plataforma."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all_tasks: List[DownloadTask] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 28)
        layout.setSpacing(14)

        title = QLabel("Historial")
        title.setObjectName("ViewTitle")
        subtitle = QLabel("Todas tus descargas anteriores, con búsqueda y filtro por plataforma.")
        subtitle.setObjectName("ViewSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        filter_box = QHBoxLayout()
        filter_box.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por título...")
        self.search_input.setClearButtonEnabled(True)

        self.combo_platform = QComboBox()
        self.combo_platform.addItems(["Todas las plataformas", "YouTube", "TikTok", "Instagram", "Facebook"])

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("HintLabel")

        filter_box.addWidget(self.search_input, stretch=2)
        filter_box.addWidget(self.combo_platform, stretch=1)
        layout.addLayout(filter_box)

        # Tabla de Historial
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Título", "Plataforma", "Calidad", "Formato", "Tamaño", "Fecha", "Estado"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        for col in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)
        layout.addWidget(self.lbl_count)

        # Filtros en vivo
        self.search_input.textChanged.connect(lambda _: self._refresh())
        self.combo_platform.currentIndexChanged.connect(lambda _: self._refresh())

    def load_history(self, tasks: List[DownloadTask]) -> None:
        self._all_tasks = sorted(tasks, key=lambda t: t.created_at, reverse=True)
        self._refresh()

    def _filtered_tasks(self) -> List[DownloadTask]:
        query = self.search_input.text().strip().lower()
        selected_platform = self.combo_platform.currentText()

        filtered: List[DownloadTask] = []
        for task in self._all_tasks:
            if query and query not in task.media.title.lower():
                continue
            if selected_platform != "Todas las plataformas" and task.media.platform != selected_platform:
                continue
            filtered.append(task)
        return filtered

    def _refresh(self) -> None:
        tasks = self._filtered_tasks()
        total = len(self._all_tasks)
        self.lbl_count.setText(f"{len(tasks)} de {total} descargas")

        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            quality = task.selected_format.resolution or "-"
            fmt = task.selected_format.extension.upper() or "-"
            size_text = format_size_bytes(task.total_bytes) if task.total_bytes > 0 else "-"
            fecha = task.created_at.strftime("%d/%m/%Y %H:%M") if task.created_at else "-"
            estado = humanize_download_state(task.status)

            values = [
                task.media.title,
                task.media.platform,
                quality,
                fmt,
                size_text,
                fecha,
                estado,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)
