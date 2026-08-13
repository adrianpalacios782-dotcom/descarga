from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar, QPushButton

from src.domain.entities.download_task import DownloadTask, DownloadState


class DownloadCardWidget(QFrame):
    """Tarjeta interactiva multimedia que muestra el progreso y controles de una descarga."""
    pause_requested = Signal(str)
    resume_requested = Signal(str)
    cancel_requested = Signal(str)
    retry_requested = Signal(str)

    def __init__(self, task: DownloadTask, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DownloadCard")
        self.task_id = task.id.value

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Fila Superior: Título y Plataforma
        top_row = QHBoxLayout()
        self.title_label = QLabel(task.media.title)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        self.platform_badge = QLabel(task.media.platform)
        self.platform_badge.setStyleSheet("font-size: 11px; color: #1db954; font-weight: 700; background-color: #1f1f1f; padding: 4px 8px; border-radius: 4px;")
        
        top_row.addWidget(self.title_label, stretch=1)
        top_row.addWidget(self.platform_badge)
        layout.addLayout(top_row)

        # Fila Central: Barra de Progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(task.progress_percent))
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        # Fila Inferior: Telemetría y Botones
        bottom_row = QHBoxLayout()
        self.status_label = QLabel(f"Estado: {task.status.value}")
        self.status_label.setStyleSheet("font-size: 12px; color: #b3b3b3;")
        self.telemetry_label = QLabel("0.0 MB / 0.0 MB · 0.0 MB/s · ETA: 00:00")
        self.telemetry_label.setStyleSheet("font-size: 12px; color: #b3b3b3;")

        self.btn_pause = QPushButton("Pausar")
        self.btn_pause.setObjectName("SecondaryButton")
        self.btn_pause.clicked.connect(lambda: self.pause_requested.emit(self.task_id))

        self.btn_resume = QPushButton("Reanudar")
        self.btn_resume.setObjectName("SecondaryButton")
        self.btn_resume.hide()
        self.btn_resume.clicked.connect(lambda: self.resume_requested.emit(self.task_id))

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.clicked.connect(lambda: self.cancel_requested.emit(self.task_id))

        self.btn_retry = QPushButton("Reintentar")
        self.btn_retry.setObjectName("SecondaryButton")
        self.btn_retry.hide()
        self.btn_retry.clicked.connect(lambda: self.retry_requested.emit(self.task_id))

        bottom_row.addWidget(self.status_label)
        bottom_row.addWidget(self.telemetry_label)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_pause)
        bottom_row.addWidget(self.btn_resume)
        bottom_row.addWidget(self.btn_retry)
        bottom_row.addWidget(self.btn_cancel)
        layout.addLayout(bottom_row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("font-size: 11px; color: #ff6b6b;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

    def update_telemetry(self, progress: float, downloaded: int, total: int, speed: float, eta: float) -> None:
        self.progress_bar.setValue(int(progress))
        speed_mb = speed / (1024 * 1024)
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        
        total_sec = int(eta)
        mins = total_sec // 60
        secs = total_sec % 60
        eta_str = f"{mins:02d}:{secs:02d}"

        self.telemetry_label.setText(f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB · {speed_mb:.2f} MB/s · ETA: {eta_str}")

    def set_state(self, state: DownloadState) -> None:
        self.status_label.setText(f"Estado: {state.value}")
        if state == DownloadState.PAUSED:
            self.btn_pause.hide()
            self.btn_resume.show()
            self.btn_retry.hide()
        elif state == DownloadState.DOWNLOADING:
            self.btn_pause.show()
            self.btn_resume.hide()
            self.btn_retry.hide()
        elif state in (DownloadState.COMPLETED, DownloadState.CANCELLED):
            self.btn_pause.hide()
            self.btn_resume.hide()
            self.btn_cancel.hide()
            self.btn_retry.hide()
        elif state == DownloadState.FAILED:
            self.btn_pause.hide()
            self.btn_resume.hide()
            self.btn_cancel.hide()
            self.btn_retry.show()
            self.progress_bar.setValue(0)

    def set_error(self, message: str) -> None:
        if message:
            self.error_label.setText(f"Error: {message}")
            self.error_label.show()
        else:
            self.error_label.hide()
