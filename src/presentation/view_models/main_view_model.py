import threading
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Slot

from src.application.use_cases import (
    AnalyzeUrlUseCase,
    CreateDownloadUseCase,
    StartDownloadUseCase,
    PauseDownloadUseCase,
    ResumeDownloadUseCase,
    CancelDownloadUseCase,
    RetryDownloadUseCase,
)
from src.domain.entities.download_task import DownloadTask
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.events.domain_events import (
    DownloadProgressChangedEvent,
    DownloadPausedEvent,
    DownloadResumedEvent,
    DownloadCompletedEvent,
    DownloadFailedEvent,
    DownloadCancelledEvent,
)
from src.domain.exceptions.domain_exceptions import TaskNotFoundError
from src.domain.ports.download_engine import IDownloadEngine
from src.domain.ports.download_repository import IDownloadRepository
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.value_objects.download_id import DownloadId
from src.infrastructure.adapters.download.download_queue_manager import (
    DownloadQueueManager,
)
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus


class MainViewModel(QObject):
    """ViewModel principal que conecta las intenciones de la UI PySide6 con los Casos de Uso."""

    # Señales de Qt para actualizar la interfaz gráfica en el hilo principal sin congelar el Event Loop
    analysis_started = Signal()
    media_analyzed = Signal(object)
    analysis_failed = Signal(str)
    download_created = Signal(object)
    download_queued = Signal(str)          # id -> tarjeta "En cola"
    download_started = Signal(str)         # id -> transición a "Descargando"
    download_progress = Signal(str, float, int, int, float, float)  # id, %, downloaded, total, speed, eta
    download_state_changed = Signal(str, str, object)  # id, estado, mensaje de error
    download_completed = Signal(str, str)
    download_failed = Signal(str, str)
    download_quality_warning = Signal(str, str)  # id, advertencia de calidad

    def __init__(
        self,
        platform_adapter: IPlatformAdapter,
        download_engine: IDownloadEngine,
        repository: IDownloadRepository,
        event_bus: InProcessEventBus,
        download_queue: Optional[DownloadQueueManager] = None,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.platform_adapter = platform_adapter
        self.download_engine = download_engine
        self.repository = repository
        self.event_bus = event_bus
        self.download_queue = download_queue

        # Inicializar Casos de Uso
        self.analyze_uc = AnalyzeUrlUseCase(self.platform_adapter)
        self.create_uc = CreateDownloadUseCase(self.repository)
        self.start_uc = StartDownloadUseCase(self.repository, self.download_engine)
        self.pause_uc = PauseDownloadUseCase(self.repository, self.download_engine)
        self.resume_uc = ResumeDownloadUseCase(self.repository, self.download_engine)
        self.cancel_uc = CancelDownloadUseCase(self.repository, self.download_engine)
        self.retry_uc = RetryDownloadUseCase(self.repository, self.download_engine)

        # Suscribir ViewModel al EventBus
        self.event_bus.subscribe(DownloadProgressChangedEvent, self._on_download_progress_event)
        self.event_bus.subscribe(DownloadPausedEvent, self._on_download_paused_event)
        self.event_bus.subscribe(DownloadResumedEvent, self._on_download_resumed_event)
        self.event_bus.subscribe(DownloadCompletedEvent, self._on_download_completed_event)
        self.event_bus.subscribe(DownloadFailedEvent, self._on_download_failed_event)
        self.event_bus.subscribe(DownloadCancelledEvent, self._on_download_cancelled_event)

        # Puente señales de la cola -> señales del ViewModel (si hay cola)
        if self.download_queue is not None:
            self.download_queue.enqueued.connect(self.download_queued.emit)
            self.download_queue.started.connect(self.download_started.emit)
            self.download_queue.quality_warning.connect(self.download_quality_warning.emit)

    @Slot(str)
    def analyze_url(self, url_str: str) -> None:
        """Ejecuta el análisis de la URL en un hilo secundario asíncrono para mantener la UI 100% fluida."""
        self.analysis_started.emit()

        def _worker() -> None:
            try:
                metadata = self.analyze_uc.execute(url_str)
                self.media_analyzed.emit(metadata)
            except Exception as ex:
                self.analysis_failed.emit(str(ex))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def create_and_start_download(self, media: MediaMetadata, format_id: str, destination_path: str) -> DownloadTask:
        """Crea y encola una nueva descarga (o la inicia directo si no hay cola)."""
        task = self.create_uc.execute(media=media, format_id=format_id, destination_path=destination_path)
        self.download_created.emit(task)
        if self.download_queue is not None:
            # La cola respeta el límite de concurrencia: queda "En cola" hasta
            # que haya slot y transiciona sola a DOWNLOADING.
            self.download_queue.enqueue(task)
        else:
            self.start_uc.execute(task.id)
        return task

    def pause_download(self, task_id_str: str) -> None:
        if self.download_queue is not None:
            self.download_queue.pause(task_id_str)
            return
        self.pause_uc.execute(DownloadId(task_id_str))

    def resume_download(self, task_id_str: str) -> None:
        if self.download_queue is not None:
            self.download_queue.resume(task_id_str)
            return
        self.resume_uc.execute(DownloadId(task_id_str))

    def cancel_download(self, task_id_str: str) -> None:
        if self.download_queue is not None:
            self.download_queue.cancel(task_id_str)
            return
        self.cancel_uc.execute(DownloadId(task_id_str))

    def retry_download(self, task_id_str: str) -> None:
        if self.download_queue is not None:
            task = self.repository.get_by_id(DownloadId(task_id_str))
            if not task:
                raise TaskNotFoundError(f"No se encontró la tarea de descarga con ID '{task_id_str}'.")
            task.reset_to_queued()
            self.repository.save(task)
            self.download_queue.enqueue(task)
            return
        self.retry_uc.execute(DownloadId(task_id_str))

    def get_all_tasks(self) -> List[DownloadTask]:
        return self.repository.get_all()

    def _on_download_progress_event(self, event: DownloadProgressChangedEvent) -> None:
        self.download_progress.emit(
            event.task_id,
            event.progress_percent,
            event.downloaded_bytes,
            event.total_bytes,
            event.speed_bps,
            event.eta_seconds
        )

    def _on_download_completed_event(self, event: DownloadCompletedEvent) -> None:
        # Una descarga completada con calidad degradada sigue siendo COMPLETED;
        # la advertencia viaja como mensaje para mostrarse inline en la tarjeta.
        self.download_state_changed.emit(event.task_id, "COMPLETED", event.warning_message or None)
        self.download_completed.emit(event.task_id, event.destination_path)

    def _on_download_failed_event(self, event: DownloadFailedEvent) -> None:
        self.download_state_changed.emit(event.task_id, "FAILED", event.error_message)
        self.download_failed.emit(event.task_id, event.error_message)

    def _on_download_paused_event(self, event: DownloadPausedEvent) -> None:
        self.download_state_changed.emit(event.task_id, "PAUSED", None)

    def _on_download_resumed_event(self, event: DownloadResumedEvent) -> None:
        self.download_state_changed.emit(event.task_id, "DOWNLOADING", None)

    def _on_download_cancelled_event(self, event: DownloadCancelledEvent) -> None:
        self.download_state_changed.emit(event.task_id, "CANCELLED", None)
