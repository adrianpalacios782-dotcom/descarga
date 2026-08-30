from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Set

from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.entities.subtitle import SubtitleConfig
from src.domain.exceptions.domain_exceptions import InvalidStateTransitionError
from src.domain.value_objects.download_id import DownloadId


class DownloadState(str, Enum):
    """Estados posibles dentro de la máquina de estados del ciclo de vida de una descarga."""
    QUEUED = "QUEUED"
    ANALYZING = "ANALYZING"
    READY = "READY"
    DOWNLOADING = "DOWNLOADING"
    PAUSED = "PAUSED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Transiciones de estado válidas permitidas
VALID_TRANSITIONS: Dict[DownloadState, Set[DownloadState]] = {
    DownloadState.QUEUED: {DownloadState.ANALYZING, DownloadState.DOWNLOADING, DownloadState.CANCELLED},
    DownloadState.ANALYZING: {DownloadState.READY, DownloadState.FAILED, DownloadState.CANCELLED},
    DownloadState.READY: {DownloadState.QUEUED, DownloadState.DOWNLOADING, DownloadState.CANCELLED},
    DownloadState.DOWNLOADING: {DownloadState.PAUSED, DownloadState.PROCESSING, DownloadState.COMPLETED, DownloadState.FAILED, DownloadState.CANCELLED},
    DownloadState.PAUSED: {DownloadState.DOWNLOADING, DownloadState.CANCELLED},
    DownloadState.PROCESSING: {DownloadState.COMPLETED, DownloadState.FAILED, DownloadState.CANCELLED},
    DownloadState.FAILED: {DownloadState.QUEUED, DownloadState.CANCELLED},
    DownloadState.COMPLETED: set(),
    DownloadState.CANCELLED: set(),
}


@dataclass
class DownloadTask:
    """Entidad principal que representa y gestiona una tarea de descarga de medios."""
    id: DownloadId
    media: MediaMetadata
    selected_format: FormatOption
    destination_path: str
    status: DownloadState = DownloadState.QUEUED
    progress_percent: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_bps: float = 0.0
    eta_seconds: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    # Advertencia de calidad (ej. "se solicitó 1080p pero se obtuvo 806p").
    # La tarea puede estar COMPLETED y aun así llevar esta advertencia visible:
    # una descarga técnicamente exitosa con calidad inferior NO es un Error.
    quality_warning: Optional[str] = None
    subtitle_config: Optional[SubtitleConfig] = None

    def __post_init__(self) -> None:
        if not self.destination_path or not self.destination_path.strip():
            raise ValueError("DownloadTask debe tener una ruta de destino no vacía.")

    def transition_to(self, new_state: DownloadState) -> None:
        """Aplica una transición de estado si cumple con las reglas de la máquina de estados."""
        if new_state == self.status:
            return

        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Transición inválida de estado: '{self.status.value}' -> '{new_state.value}'"
            )

        self.status = new_state

        if new_state == DownloadState.DOWNLOADING and self.started_at is None:
            self.started_at = datetime.now()
        elif new_state == DownloadState.COMPLETED:
            self.completed_at = datetime.now()
            self.progress_percent = 100.0
            self.eta_seconds = 0.0
            self.speed_bps = 0.0

    def update_progress(self, downloaded_bytes: int, total_bytes: int, speed_bps: float, eta_seconds: float) -> None:
        """Actualiza el progreso de la descarga en tiempo real."""
        if self.status != DownloadState.DOWNLOADING:
            return

        self.downloaded_bytes = max(0, downloaded_bytes)
        self.total_bytes = max(0, total_bytes)
        self.speed_bps = max(0.0, speed_bps)
        self.eta_seconds = max(0.0, eta_seconds)

        if self.total_bytes > 0:
            pct = (self.downloaded_bytes / self.total_bytes) * 100.0
            self.progress_percent = min(100.0, max(0.0, pct))

    def pause(self) -> None:
        """Pausa la descarga activa. No-op si no está descargando o ya terminó."""
        if self.status in (DownloadState.DOWNLOADING, DownloadState.PROCESSING):
            self.transition_to(DownloadState.PAUSED)

    def resume(self) -> None:
        """Reanuda la descarga pausada. No-op si no está pausada."""
        if self.status == DownloadState.PAUSED:
            self.transition_to(DownloadState.DOWNLOADING)

    def cancel(self) -> None:
        """Cancela la descarga. No-op si ya está en un estado terminal."""
        if self.status not in (DownloadState.COMPLETED, DownloadState.FAILED, DownloadState.CANCELLED):
            self.transition_to(DownloadState.CANCELLED)

    def complete(self) -> None:
        """Marca la descarga como completada."""
        if self.status == DownloadState.DOWNLOADING:
            # Si requiriese processing, se transiciona a PROCESSING primero o directo si no requiere
            self.transition_to(DownloadState.COMPLETED)
        elif self.status == DownloadState.PROCESSING:
            self.transition_to(DownloadState.COMPLETED)

    def fail(self, error_message: str) -> None:
        """Marca la descarga como fallada almacenando el mensaje de error."""
        self.error_message = error_message
        self.transition_to(DownloadState.FAILED)

    def reset_to_queued(self) -> None:
        """Permite re-encolar explícitamente una tarea fallada o completada."""
        self.status = DownloadState.QUEUED
        self.progress_percent = 0.0
        self.downloaded_bytes = 0
        self.speed_bps = 0.0
        self.eta_seconds = 0.0
        self.error_message = None
        self.quality_warning = None
        self.started_at = None
        self.completed_at = None
