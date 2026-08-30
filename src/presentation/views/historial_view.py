import os
from typing import List

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.download_task import DownloadTask
from src.domain.services.content_preview import format_size_bytes
from src.presentation.components.status_labels import humanize_download_state


class HistorialView(QWidget):
    """Vista para consultar y gestionar el historial de descargas con búsqueda, filtro y menú contextual."""

    open_file_requested = Signal(str)
    open_folder_requested = Signal(str)
    redownload_requested = Signal(str)
    delete_task_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_tasks: List[DownloadTask] = []
        self._current_displayed_tasks: List[DownloadTask] = []

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
        self.combo_platform.addItems([
            "Todas las plataformas", "YouTube", "TikTok", "Instagram", "Facebook"
        ])

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
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        for col in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
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
            title_match = query in task.media.title.lower()
            author_match = bool(task.media.author and query in task.media.author.lower())
            if query and not (title_match or author_match):
                continue
            if selected_platform != "Todas las plataformas" and task.media.platform != selected_platform:
                continue
            filtered.append(task)
        return filtered

    def _refresh(self) -> None:
        self._current_displayed_tasks = self._filtered_tasks()
        tasks = self._current_displayed_tasks
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

    def _show_context_menu(self, pos: QPoint) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self._current_displayed_tasks):
            return

        task = self._current_displayed_tasks[row]
        menu = QMenu(self)

        # 1. Abrir archivo (si existe)
        file_path = task.destination_path
        file_exists = bool(file_path and os.path.isfile(file_path))
        act_open_file = menu.addAction("▶ Abrir archivo")
        act_open_file.setEnabled(file_exists)
        act_open_file.triggered.connect(lambda: self.open_file_requested.emit(file_path))

        # 2. Mostrar en carpeta
        act_open_folder = menu.addAction("📂 Mostrar en carpeta")
        act_open_folder.setEnabled(bool(file_path))
        act_open_folder.triggered.connect(lambda: self.open_folder_requested.emit(file_path))

        menu.addSeparator()

        # 3. Copiar enlace original
        url_value = task.media.url.value if hasattr(task.media, "url") else str(getattr(task.media, "original_url", ""))
        act_copy_url = menu.addAction("📋 Copiar enlace original")
        act_copy_url.triggered.connect(lambda: self._copy_url_to_clipboard(url_value))

        # 4. Volver a descargar
        act_redownload = menu.addAction("🔄 Volver a descargar")
        act_redownload.triggered.connect(lambda: self.redownload_requested.emit(url_value))

        menu.addSeparator()

        # 5. Eliminar del historial
        act_delete = menu.addAction("🗑 Eliminar del historial")
        act_delete.triggered.connect(lambda: self._confirm_and_delete(task))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        row = item.row()
        if 0 <= row < len(self._current_displayed_tasks):
            task = self._current_displayed_tasks[row]
            file_path = task.destination_path
            if file_path and os.path.isfile(file_path):
                self.open_file_requested.emit(file_path)
            elif file_path:
                self.open_folder_requested.emit(file_path)

    def _copy_url_to_clipboard(self, url: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(url)

    def _confirm_and_delete(self, task: DownloadTask) -> None:
        reply = QMessageBox.question(
            self,
            "Eliminar del historial",
            f"¿Deseas eliminar '{task.media.title}' del historial?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_task_requested.emit(task.id.value)
