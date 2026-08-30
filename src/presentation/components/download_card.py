from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.download_task import DownloadTask, DownloadState
from src.presentation.components.status_labels import humanize_download_state
from src.presentation.styles.styles import DARK_PALETTE


PLATFORM_ACCENT = {
    "youtube": "#ff4d4d",
    "tiktok": "#25f4ee",
    "instagram": "#e1306c",
    "facebook": "#1877f2",
}


class DownloadCardWidget(QFrame):
    """Tarjeta interactiva que muestra progreso, telemetría y controles de una descarga."""
    pause_requested = Signal(str)
    resume_requested = Signal(str)
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    open_file_requested = Signal(str)
    open_folder_requested = Signal(str)

    def __init__(self, task: DownloadTask, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DownloadCard")
        self.task_id = task.id.value
        self.destination_path = task.destination_path

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Bloque de miniatura con inicial de plataforma
        self.thumb = self._build_thumbnail_block(task.media.platform)
        layout.addWidget(self.thumb)

        body = QVBoxLayout()
        body.setSpacing(8)

        top_row = QHBoxLayout()
        self.title_label = QLabel(task.media.title)
        self.title_label.setObjectName("DownloadCardTitle")
        self.platform_badge = QLabel(task.media.platform)
        self.platform_badge.setObjectName("PlatformBadge")

        top_row.addWidget(self.title_label, stretch=1)
        top_row.addWidget(self.platform_badge)
        body.addLayout(top_row)

        # Línea de metadatos: plataforma · calidad · formato
        fmt = task.selected_format
        resolution = (fmt.resolution or "").strip() if fmt is not None else ""
        extension = (fmt.extension or "").strip().upper() if fmt is not None else ""
        meta_parts = [p for p in (task.media.platform, resolution, extension) if p]
        self.meta_label = QLabel(" · ".join(meta_parts))
        self.meta_label.setObjectName("DownloadMeta")
        body.addWidget(self.meta_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(task.progress_percent))
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        body.addWidget(self.progress_bar)

        bottom_row = QHBoxLayout()
        self.status_label = QLabel(self._status_text(task.status))
        self.status_label.setObjectName("StatusLabel")
        # Velocidad destacada: la métrica que el usuario más mira durante una descarga.
        self.speed_label = QLabel("— MB/s")
        self.speed_label.setObjectName("SpeedLabel")
        self.telemetry_label = QLabel("0.0 MB / 0.0 MB · 0.00 MB/s · ETA 00:00")
        self.telemetry_label.setObjectName("TelemetryLabel")

        self.btn_pause = QPushButton("Pausar")
        self.btn_pause.setObjectName("SecondaryButton")
        self.btn_pause.clicked.connect(lambda: self.pause_requested.emit(self.task_id))

        self.btn_resume = QPushButton("Reanudar")
        self.btn_resume.setObjectName("SecondaryButton")
        self.btn_resume.hide()
        self.btn_resume.clicked.connect(lambda: self.resume_requested.emit(self.task_id))

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.setProperty("danger", True)
        self.btn_cancel.clicked.connect(lambda: self.cancel_requested.emit(self.task_id))

        self.btn_retry = QPushButton("Reintentar")
        self.btn_retry.setObjectName("SecondaryButton")
        self.btn_retry.hide()
        self.btn_retry.clicked.connect(lambda: self.retry_requested.emit(self.task_id))

        self.btn_show_file = QPushButton("Mostrar archivo")
        self.btn_show_file.setObjectName("SecondaryButton")
        self.btn_show_file.hide()
        self.btn_show_file.clicked.connect(
            lambda: self.open_file_requested.emit(self.destination_path)
        )

        self.btn_open_folder = QPushButton("Abrir carpeta")
        self.btn_open_folder.setObjectName("LinkButton")
        self.btn_open_folder.hide()
        self.btn_open_folder.clicked.connect(
            lambda: self.open_folder_requested.emit(self.destination_path)
        )

        bottom_row.addWidget(self.status_label)
        bottom_row.addWidget(self.speed_label)
        bottom_row.addWidget(self.telemetry_label)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_show_file)
        bottom_row.addWidget(self.btn_open_folder)
        bottom_row.addWidget(self.btn_pause)
        bottom_row.addWidget(self.btn_resume)
        bottom_row.addWidget(self.btn_retry)
        bottom_row.addWidget(self.btn_cancel)
        body.addLayout(bottom_row)

        self.error_label = QLabel("")
        self.error_label.setObjectName("CardErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        body.addWidget(self.error_label)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("CardWarningLabel")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        body.addWidget(self.warning_label)

        body.addStretch()
        layout.addLayout(body, stretch=1)

    @staticmethod
    def _build_thumbnail_block(platform: str) -> QLabel:
        initial = (platform or "?")[:1].upper() or "?"
        accent = PLATFORM_ACCENT.get((platform or "").lower(), "#1db954")
        pixmap_size = 64

        from PySide6.QtGui import QPixmap
        pixmap = QPixmap(pixmap_size, pixmap_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(DARK_PALETTE.surface_active))
        painter.drawRoundedRect(0, 0, pixmap_size, pixmap_size, 10, 10)
        font = QFont("Segoe UI", int(pixmap_size * 0.42))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(accent))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, initial)
        painter.end()

        thumb = QLabel()
        thumb.setObjectName("ThumbBlock")
        thumb.setPixmap(pixmap)
        thumb.setFixedSize(pixmap_size, pixmap_size)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return thumb

    def _status_text(self, state: DownloadState) -> str:
        return humanize_download_state(state)

    def update_telemetry(self, progress: float, downloaded: int, total: int, speed: float, eta: float) -> None:
        self.progress_bar.setValue(int(progress))
        speed_mb = speed / (1024 * 1024)
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)

        self.speed_label.setText(f"{speed_mb:.1f} MB/s")

        total_sec = max(0, int(eta))
        mins = total_sec // 60
        secs = total_sec % 60
        eta_str = f"{mins:02d}:{secs:02d}"

        self.telemetry_label.setText(f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB · {speed_mb:.2f} MB/s · ETA {eta_str}")

    def set_state(self, state: DownloadState) -> None:
        self.status_label.setText(self._status_text(state))
        completed = state == DownloadState.COMPLETED and bool(self.destination_path)
        if completed:
            self.btn_show_file.show()
            self.btn_open_folder.show()

        if state in (DownloadState.COMPLETED, DownloadState.CANCELLED):
            self.progress_bar.setValue(100 if state == DownloadState.COMPLETED else self.progress_bar.value())
            self.btn_pause.hide()
            self.btn_resume.hide()
            self.btn_cancel.hide()
            self.btn_retry.hide()
        elif state == DownloadState.PAUSED:
            self.btn_pause.hide()
            self.btn_resume.show()
            self.btn_retry.hide()
            self.btn_cancel.show()
        elif state == DownloadState.DOWNLOADING:
            self.btn_pause.show()
            self.btn_resume.hide()
            self.btn_retry.hide()
            self.btn_cancel.show()
        elif state == DownloadState.FAILED:
            self.btn_pause.hide()
            self.btn_resume.hide()
            self.btn_cancel.hide()
            self.btn_retry.show()
            self.btn_cancel.show()
            self.progress_bar.setValue(0)
        elif state in (DownloadState.QUEUED, DownloadState.ANALYZING, DownloadState.READY, DownloadState.PROCESSING):
            self.btn_pause.hide()
            self.btn_resume.hide()
            self.btn_retry.hide()
            self.btn_cancel.show()

    def set_error(self, message: str) -> None:
        if message:
            self.error_label.setText(message)
            self.error_label.show()
        else:
            self.error_label.hide()

    def set_quality_warning(self, message: str) -> None:
        """Muestra una advertencia de calidad inline (descarga completada con calidad inferior)."""
        if message:
            self.warning_label.setText(message)
            self.warning_label.show()
        else:
            self.warning_label.hide()
