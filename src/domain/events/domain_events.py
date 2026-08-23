from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Clase base inmutable para todos los eventos del dominio de negocio."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True, kw_only=True)
class DownloadCreatedEvent(DomainEvent):
    """Emitido cuando se crea una nueva tarea de descarga."""
    task_id: str
    url: str
    destination_path: str


@dataclass(frozen=True, kw_only=True)
class DownloadQueuedEvent(DomainEvent):
    """Emitido cuando una descarga es ingresada en la cola activa."""
    task_id: str


@dataclass(frozen=True, kw_only=True)
class DownloadStartedEvent(DomainEvent):
    """Emitido cuando un worker inicia la transferencia de datos de una descarga."""
    task_id: str


@dataclass(frozen=True, kw_only=True)
class DownloadProgressChangedEvent(DomainEvent):
    """Emitido periódicamente con los datos de progreso de una descarga activa."""
    task_id: str
    progress_percent: float
    downloaded_bytes: int
    total_bytes: int
    speed_bps: float
    eta_seconds: float


@dataclass(frozen=True, kw_only=True)
class DownloadPausedEvent(DomainEvent):
    """Emitido cuando una descarga es pausada."""
    task_id: str


@dataclass(frozen=True, kw_only=True)
class DownloadResumedEvent(DomainEvent):
    """Emitido cuando una descarga es reanudada."""
    task_id: str


@dataclass(frozen=True, kw_only=True)
class DownloadCompletedEvent(DomainEvent):
    """Emitido cuando una descarga finaliza exitosamente.

    warning_message transporta una advertencia no bloqueante (ej. calidad
    degradada: se solicitó 1080p y el archivo final tiene menos resolución).
    """
    task_id: str
    destination_path: str
    total_bytes: int
    warning_message: str = ""


@dataclass(frozen=True, kw_only=True)
class DownloadFailedEvent(DomainEvent):
    """Emitido cuando ocurre una falla en el proceso de descarga o procesamiento."""
    task_id: str
    error_message: str


@dataclass(frozen=True, kw_only=True)
class DownloadCancelledEvent(DomainEvent):
    """Emitido cuando una descarga es cancelada."""
    task_id: str

