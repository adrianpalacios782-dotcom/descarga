from typing import Dict
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame

from src.domain.entities.download_task import DownloadTask
from src.presentation.components.download_card import DownloadCardWidget


class DescargasView(QWidget):
    """Vista de monitoreo y control operacional de descargas en curso y en cola."""
    pause_requested = Signal(str)
    resume_requested = Signal(str)
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    open_file_requested = Signal(str)
    open_folder_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.cards: Dict[str, DownloadCardWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Descargas")
        title.setObjectName("ViewTitle")
        subtitle = QLabel("Progreso en tiempo real de tus descargas activas y en cola.")
        subtitle.setObjectName("ViewSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Estado vacío de la biblioteca (se retira al llegar la primera tarjeta)
        self.lbl_empty = QLabel(
            "No hay descargas todavía.\n"
            "Vuelve a Inicio, pega un enlace y pulsa Descargar."
        )
        self.lbl_empty.setObjectName("EmptyStateHint")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setWordWrap(True)
        layout.addSpacing(24)
        layout.addWidget(self.lbl_empty)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(12)
        self.card_layout.addStretch()

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def add_task(self, task: DownloadTask) -> None:
        if task.id.value in self.cards:
            return

        if not self.cards:
            self.lbl_empty.hide()

        card = DownloadCardWidget(task)
        card.pause_requested.connect(self.pause_requested.emit)
        card.resume_requested.connect(self.resume_requested.emit)
        card.cancel_requested.connect(self.cancel_requested.emit)
        card.retry_requested.connect(self.retry_requested.emit)
        card.open_file_requested.connect(self.open_file_requested.emit)
        card.open_folder_requested.connect(self.open_folder_requested.emit)

        self.cards[task.id.value] = card
        self.card_layout.insertWidget(self.card_layout.count() - 1, card)

    def set_state(self, task_id: str, state: str, error_message: str | None = None) -> None:
        if task_id not in self.cards:
            return
        from src.domain.entities.download_task import DownloadState
        self.cards[task_id].set_state(DownloadState(state))
        if state == "COMPLETED":
            # En COMPLETED el mensaje es una advertencia de calidad (no un error).
            self.cards[task_id].set_quality_warning(error_message or "")
            self.cards[task_id].set_error("")
        else:
            self.cards[task_id].set_quality_warning("")
            self.cards[task_id].set_error(error_message or "")

    def update_progress(self, task_id: str, progress: float, downloaded: int, total: int, speed: float, eta: float) -> None:
        if task_id in self.cards:
            self.cards[task_id].update_telemetry(progress, downloaded, total, speed, eta)

    def show_quality_warning(self, task_id: str, message: str) -> None:
        """Muestra una advertencia de calidad sin alterar el estado de la tarjeta."""
        if task_id in self.cards:
            self.cards[task_id].set_quality_warning(message or "")
