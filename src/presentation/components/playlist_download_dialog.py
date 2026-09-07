import os
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.playlist_metadata import PlaylistMetadata


class PlaylistDownloadDialog(QDialog):
    """Diálogo modal para inspeccionar y descargar elementos de una lista de reproducción / álbum."""

    playlist_download_requested = Signal(list, str, str)  # (selected_urls: List[str], quality: str, dest_dir: str)

    def __init__(
        self,
        playlist: PlaylistMetadata,
        default_dir: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.playlist = playlist
        self.setWindowTitle(f"Descargar Playlist — {playlist.title}")
        self.resize(750, 580)
        self.setMinimumSize(600, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Encabezado
        title = QLabel(f"Playlist: {playlist.title}")
        title.setObjectName("ViewTitle")
        subtitle_text = f"Canal / Autor: {playlist.author or 'Desconocido'}  •  {playlist.item_count} elementos encontrados"
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("ViewSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Controles de selección rápida
        sel_row = QHBoxLayout()
        self.btn_select_all = QPushButton("Seleccionar Todos")
        self.btn_select_all.setObjectName("SecondaryButton")
        self.btn_select_all.clicked.connect(self._select_all)

        self.btn_deselect_all = QPushButton("Deseleccionar Todos")
        self.btn_deselect_all.setObjectName("SecondaryButton")
        self.btn_deselect_all.clicked.connect(self._deselect_all)

        self.lbl_selected_count = QLabel(f"{playlist.item_count} de {playlist.item_count} seleccionados")
        self.lbl_selected_count.setObjectName("HintLabel")

        sel_row.addWidget(self.btn_select_all)
        sel_row.addWidget(self.btn_deselect_all)
        sel_row.addStretch()
        sel_row.addWidget(self.lbl_selected_count)
        layout.addLayout(sel_row)

        # Tabla de elementos
        self.table = QTableWidget(len(playlist.entries), 4)
        self.table.setHorizontalHeaderLabels(["#", "Título", "Duración", "Canal / Autor"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self._populate_table()
        layout.addWidget(self.table, stretch=1)

        # Opciones de descarga
        options_card = QFrame()
        options_card.setObjectName("Card")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(14, 12, 14, 12)
        options_layout.setSpacing(10)

        # Selector de Calidad
        quality_row = QHBoxLayout()
        lbl_quality = QLabel("Calidad de descarga:")
        self.combo_quality = QComboBox()
        self.combo_quality.addItems([
            "Mejor calidad disponible (Video)",
            "1080p (Full HD)",
            "720p (HD)",
            "480p (SD)",
            "Solo Audio — MP3 (320 kbps)",
            "Solo Audio — FLAC (Lossless)",
        ])
        quality_row.addWidget(lbl_quality)
        quality_row.addWidget(self.combo_quality, stretch=1)
        options_layout.addLayout(quality_row)

        # Carpeta Destino
        dir_row = QHBoxLayout()
        lbl_dir = QLabel("Carpeta destino:")
        resolved_dir = default_dir or os.path.join(os.path.expanduser("~"), "Downloads")
        self.txt_dir = QLineEdit(os.path.normpath(resolved_dir))
        self.btn_browse = QPushButton("Examinar...")
        self.btn_browse.setObjectName("SecondaryButton")
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self._on_browse_clicked)
        dir_row.addWidget(lbl_dir)
        dir_row.addWidget(self.txt_dir, stretch=1)
        dir_row.addWidget(self.btn_browse)
        options_layout.addLayout(dir_row)

        layout.addWidget(options_card)

        # Botones de Acción
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_start = QPushButton(f"Descargar Seleccionados ({playlist.item_count})")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._on_start_clicked)
        btn_row.addWidget(self.btn_start)

        layout.addLayout(btn_row)

    def _populate_table(self) -> None:
        for row_idx, entry in enumerate(self.playlist.entries):
            # Checkbox + Index
            item_check = QTableWidgetItem(f"{row_idx + 1}")
            item_check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row_idx, 0, item_check)

            # Título
            item_title = QTableWidgetItem(entry.title or "Sin título")
            self.table.setItem(row_idx, 1, item_title)

            # Duración
            dur_str = f"{int(entry.duration_seconds // 60)}:{int(entry.duration_seconds % 60):02d}" if entry.duration_seconds else "--:--"
            item_dur = QTableWidgetItem(dur_str)
            self.table.setItem(row_idx, 2, item_dur)

            # Autor
            item_author = QTableWidgetItem(entry.uploader or self.playlist.author or "")
            self.table.setItem(row_idx, 3, item_author)

        self.table.itemChanged.connect(self._on_item_changed)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            count = len(self.get_selected_urls())
            total = len(self.playlist.entries)
            self.lbl_selected_count.setText(f"{count} de {total} seleccionados")
            self.btn_start.setText(f"Descargar Seleccionados ({count})")
            self.btn_start.setEnabled(count > 0)

    def _select_all(self) -> None:
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
        self.table.blockSignals(False)
        total = len(self.playlist.entries)
        self.lbl_selected_count.setText(f"{total} de {total} seleccionados")
        self.btn_start.setText(f"Descargar Seleccionados ({total})")
        self.btn_start.setEnabled(total > 0)

    def _deselect_all(self) -> None:
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.table.blockSignals(False)
        total = len(self.playlist.entries)
        self.lbl_selected_count.setText(f"0 de {total} seleccionados")
        self.btn_start.setText("Descargar Seleccionados (0)")
        self.btn_start.setEnabled(False)

    def get_selected_urls(self) -> List[str]:
        selected: List[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                if row < len(self.playlist.entries):
                    selected.append(self.playlist.entries[row].url)
        return selected

    def _on_browse_clicked(self) -> None:
        current_dir = self.txt_dir.text().strip() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Carpeta de Destino",
            current_dir,
        )
        if folder:
            self.txt_dir.setText(os.path.normpath(folder))

    def _on_start_clicked(self) -> None:
        urls = self.get_selected_urls()
        if not urls:
            return

        dest_dir = self.txt_dir.text().strip()
        if not os.path.isdir(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except OSError as ex:
                QMessageBox.warning(self, "Carpeta inválida", f"No se pudo crear la carpeta destino:\n{ex}")
                return

        quality = self.combo_quality.currentText()
        self.playlist_download_requested.emit(urls, quality, dest_dir)
        self.accept()
