"""Gestor de cola de descargas con concurrencia limitada y cancelacion limpia.

Orquesta el motor de descargas (`IDownloadEngine`) sobre un `QThreadPool`:

- LIMITE DE CONCURRENCIA configurable (por defecto 2 descargas simultaneas).
  Las tareas adicionales quedan en estado QUEUED ("En cola") y transicionan a
  DOWNLOADING automaticamente conforme se liberan slots.
- SENALES QT NO BLOQUEANTES hacia la UI (progreso formateado, advertencias de
  calidad, finalizacion, error y cancelacion). Las senales se emiten desde
  hilos worker; Qt las entrega a receptores del hilo GUI via QueuedConnection.
- CANCELACION LIMPIA: token/evento hacia el motor para tareas activas,
  retirada inmediata de tareas en cola, purga de archivos residuales en disco
  (*.part, *.ytdl, *.temp.*) e ignorancia segura de eventos tardios.

El manager NO duplica la maquina de estados: consume los eventos de dominio
que publica el motor en el bus y solo persiste/transiciona cuando toca
(QUEUED al encolar, DOWNLOADING al despachar, terminal al finalizar).
"""
import logging
import os
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Protocol

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from src.domain.entities.download_task import DownloadState, DownloadTask
from src.domain.events.domain_events import (
    DownloadCancelledEvent,
    DownloadCompletedEvent,
    DownloadFailedEvent,
    DownloadProgressChangedEvent,
    DownloadQueuedEvent,
    DownloadStartedEvent,
)
from src.domain.ports.download_engine import IDownloadEngine
from src.domain.ports.download_repository import IDownloadRepository
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus

logger = logging.getLogger(__name__)

# Patrones de archivos residuales que se purgan al cancelar/fallar.
_TEMP_SUFFIXES = (".part", ".ytdl", ".tmp")
_TEMP_INFIX_RE = re.compile(r"\.temp\.")

_UNITS = ("B", "KB", "MB", "GB", "TB")


# ================================================================ Helpers puros
def humanize_bytes(num_bytes: float | None) -> str:
    """Formatea bytes como texto legible ('150 B', '12.5 MB', '1.8 GB')."""
    if num_bytes is None or num_bytes < 0:
        return "?"
    value = float(num_bytes)
    for unit in _UNITS:
        if value < 1024.0 or unit == _UNITS[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return "?"  # inalcanzable; salvaguarda de tipado


def format_eta(seconds: float | None) -> str:
    """Formatea segundos restantes como 'm:ss' u 'h:mm:ss'; '--:--' si es desconocido."""
    if seconds is None or seconds <= 0:
        return "--:--"
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def purge_temporary_files(destination_path: str) -> list[str]:
    """Elimina archivos temporales residuales asociados a una descarga.

    Recorre SOLO el directorio destino (sin recursion), borrando entradas cuyo
    nombre empiece por la base sanitizada del destino y termine en .part/.ytdl/
    .tmp o contenga '.temp.'. Nunca borra el archivo final ni nada fuera del
    directorio. Devuelve los nombres eliminados.
    """
    from src.infrastructure.adapters.download.ytdlp_download_engine import (
        YtDlpDownloadEngine,
    )

    deleted: list[str] = []
    try:
        dest_dir, base, _ext = YtDlpDownloadEngine._split_destination(destination_path)
        if not base or not os.path.isdir(dest_dir):
            return deleted
        for entry in os.listdir(dest_dir):
            full = os.path.join(dest_dir, entry)
            if not entry.startswith(base) or not os.path.isfile(full):
                continue
            lowered = entry.lower()
            is_temp = lowered.endswith(_TEMP_SUFFIXES) or bool(
                _TEMP_INFIX_RE.search(lowered)
            )
            if not is_temp:
                continue
            try:
                os.remove(full)
                deleted.append(entry)
            except OSError as ex:
                logger.warning("No se pudo purgar '%s': %s", full, ex)
    except Exception as ex:  # noqa: BLE001 - la purga jamas rompe el flujo
        logger.warning("Purga de temporales abortada: %s", ex)
    return deleted


# ================================================================ Pool inyectable
class RunnablePool(Protocol):
    """Contrato minimo del pool de ejecucion (QThreadPool lo satisface)."""

    def start(self, runnable: QRunnable) -> None: ...

    def setMaxThreadCount(self, threads: int) -> None: ...  # noqa: N802


class DownloadTaskRunnable(QRunnable):
    """Worker del pool: dispara el motor y retiene el slot hasta el evento terminal.

    El motor real ejecuta su propio hilo interno; el runnable bloquea el slot
    del pool hasta que el bus anuncia el estado terminal (o cancelacion previa),
    de modo que el limite de concurrencia refleje descargas ACTIVAS reales.
    """

    def __init__(self, manager: "DownloadQueueManager", task: DownloadTask) -> None:
        super().__init__()
        self._manager = manager
        self._task = task

    def run(self) -> None:  # noqa: D102 - punto de entrada de QThreadPool
        self._manager.run_worker(self._task)


# ================================================================ Manager
@dataclass
class _ActiveEntry:
    task: DownloadTask
    done: threading.Event
    pre_cancelled: bool = field(default=False)


class DownloadQueueManager(QObject):
    """Cola FIFO de descargas con slots limitados y cancelacion limpia."""

    # Firma exacta solicitada para la UI:
    progress = Signal(str, float, float, str, str, str)  # id, %, speed(B/s), eta, downloaded, total
    quality_warning = Signal(str, str)                   # id, mensaje
    finished = Signal(str, str)                          # id, output_path
    error = Signal(str, str)                             # id, mensaje de error
    cancelled = Signal(str)                              # id
    # Extras de ciclo de vida para pintar "En cola" -> "Descargando":
    enqueued = Signal(str)
    started = Signal(str)

    def __init__(
        self,
        engine: IDownloadEngine,
        event_bus: InProcessEventBus | None = None,
        repository: IDownloadRepository | None = None,
        max_concurrent: int = 2,
        pool: Any = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if max_concurrent < 1:
            raise ValueError("max_concurrent debe ser >= 1")
        self._engine = engine
        self._bus = event_bus
        self._repository = repository
        self._pool: RunnablePool = pool if pool is not None else QThreadPool()
        self._max_concurrent = max_concurrent
        self._pool.setMaxThreadCount(max_concurrent)

        self._pending: OrderedDict[str, DownloadTask] = OrderedDict()
        self._active: dict[str, _ActiveEntry] = {}
        self._lock = threading.RLock()

        if self._bus is not None:
            self._bus.subscribe(DownloadProgressChangedEvent, self._on_progress_event)
            self._bus.subscribe(DownloadCompletedEvent, self._on_completed_event)
            self._bus.subscribe(DownloadFailedEvent, self._on_failed_event)
            self._bus.subscribe(DownloadCancelledEvent, self._on_cancelled_event)

    # ------------------------------------------------------------ Propiedades
    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @max_concurrent.setter
    def max_concurrent(self, value: int) -> None:
        self.set_max_concurrent(value)

    def set_max_concurrent(self, value: int) -> None:
        """Ajusta el limite en caliente; subirlo despacha pendientes de inmediato."""
        if value < 1:
            raise ValueError("max_concurrent debe ser >= 1")
        with self._lock:
            self._max_concurrent = value
        try:
            self._pool.setMaxThreadCount(value)
        except Exception:  # noqa: BLE001 - pools de prueba pueden no implementarlo
            pass
        self._dispatch()

    def active_ids(self) -> list[str]:
        with self._lock:
            return list(self._active.keys())

    def pending_ids(self) -> list[str]:
        with self._lock:
            return list(self._pending.keys())

    # ------------------------------------------------------------ Cola publica
    def enqueue(self, task: DownloadTask) -> None:
        """Encola una tarea QUEUED; la despacha si hay slot libre."""
        task_id = task.id.value
        with self._lock:
            if task_id in self._active or task_id in self._pending:
                logger.debug("Tarea %s ya esta gestionada; enqueue ignorado.", task_id)
                return
            if task.status in (DownloadState.COMPLETED, DownloadState.FAILED, DownloadState.CANCELLED):
                raise ValueError(f"La tarea {task_id} esta en estado terminal '{task.status.value}'.")
            self._pending[task_id] = task

        if task.status != DownloadState.QUEUED:
            try:
                task.transition_to(DownloadState.QUEUED)
            except Exception:  # noqa: BLE001 - READY->QUEUED etc. ya lo permiten
                task.status = DownloadState.QUEUED
        self._save(task)
        self._publish(DownloadQueuedEvent(task_id=task_id))
        self.enqueued.emit(task_id)
        logger.info("Cola: tarea %s encolada (%d pendientes).", task_id, len(self.pending_ids()))
        self._dispatch()

    def cancel(self, task_id: str) -> bool:
        """Cancela una tarea activa o en cola con limpieza completa.

        Devuelve True si la tarea estaba gestionada por la cola.
        """
        with self._lock:
            pending_task = self._pending.pop(task_id, None)
            entry = self._active.get(task_id)

        if pending_task is not None:
            self._finalize_cancellation(pending_task)
            return True
        if entry is not None:
            entry.pre_cancelled = True
            try:
                self._engine.cancel(entry.task)
            except Exception as ex:  # noqa: BLE001 - el evento tardio igual cierra
                logger.warning("Motor rechazo la cancelacion de %s: %s", task_id, ex)
            return True
        return False

    def pause(self, task_id: str) -> bool:
        entry = self._entry_if_active(task_id)
        if entry is None:
            return False
        try:
            self._engine.pause(entry.task)
        except Exception as ex:  # noqa: BLE001
            logger.warning("Pausa fallida para %s: %s", task_id, ex)
            return False
        return True

    def resume(self, task_id: str) -> bool:
        entry = self._entry_if_active(task_id)
        if entry is None:
            return False
        try:
            self._engine.resume(entry.task)
        except Exception as ex:  # noqa: BLE001
            logger.warning("Reanudacion fallida para %s: %s", task_id, ex)
            return False
        return True

    # ---------------------------------------------------- Punto de entrada worker
    def run_worker(self, task: DownloadTask) -> None:
        """Ejecutado por el hilo del pool: lanza el motor y retiene el slot.

        Si la tarea fue pre-cancelada antes de arrancar el worker, el motor
        NUNCA se invoca (huerfano cero).
        """
        task_id = task.id.value
        entry = self._entry_if_active(task_id)
        if entry is None:
            return
        if not entry.pre_cancelled:
            try:
                self._engine.download(task)
            except Exception as ex:  # noqa: BLE001 - el motor ya no llegara a publicar
                logger.error("Motor lanzo excepcion inmediata para %s: %s", task_id, ex)
                self._handle_failed_locally(task, str(ex))
                return
        entry.done.wait(timeout=300.0)

    # ------------------------------------------------------------ Internos cola
    def _dispatch(self) -> None:
        """Promueve pendientes a activos mientras haya slots libres."""
        launched: list[DownloadTask] = []
        with self._lock:
            while len(self._active) < self._max_concurrent and self._pending:
                _task_id, task = self._pending.popitem(last=False)
                self._active[task.id.value] = _ActiveEntry(task=task, done=threading.Event())
                launched.append(task)
        for task in launched:
            self._begin_active_task(task)

    def _begin_active_task(self, task: DownloadTask) -> None:
        task_id = task.id.value
        entry = self._entry_if_active(task_id)
        if entry is None or entry.pre_cancelled:
            # Cancelado en la ventana entre despacho y arranque del worker.
            self._handle_cancelled_terminal(task_id)
            return
        try:
            task.transition_to(DownloadState.DOWNLOADING)
        except Exception:  # noqa: BLE001 - reintentos ya parten de DOWNLOADING
            pass
        self._save(task)
        self._publish(DownloadStartedEvent(task_id=task_id))
        self.started.emit(task_id)
        logger.info("Cola: tarea %s despachada (%d/%d slots).",
                    task_id, len(self.active_ids()), self._max_concurrent)
        try:
            self._pool.start(DownloadTaskRunnable(self, task))
        except Exception as ex:  # noqa: BLE001 - sin pool no hay descarga
            logger.error("No se pudo iniciar el worker de %s: %s", task_id, ex)
            self._handle_failed_locally(task, f"No se pudo iniciar el worker: {ex}")

    def _entry_if_active(self, task_id: str) -> _ActiveEntry | None:
        with self._lock:
            return self._active.get(task_id)

    def _release_slot(self, task_id: str) -> None:
        with self._lock:
            entry = self._active.pop(task_id, None)
        if entry is not None:
            entry.done.set()
        else:
            # Evento tardio tras cierre normal: ignorar con seguridad.
            logger.debug("Evento terminal tardio para %s (ya no activa).", task_id)

    # ------------------------------------------------------- Terminales locales
    def _finalize_cancellation(self, task: DownloadTask) -> None:
        """Cancelacion definitiva de tarea EN COLA (nunca llego al motor)."""
        purge_temporary_files(task.destination_path)
        try:
            task.cancel()
        except Exception:  # noqa: BLE001
            task.status = DownloadState.CANCELLED
        self._save(task)
        self._publish(DownloadCancelledEvent(task_id=task.id.value))
        self.cancelled.emit(task.id.value)
        logger.info("Cola: tarea %s cancelada estando en cola.", task.id.value)

    def _handle_failed_locally(self, task: DownloadTask, message: str) -> None:
        """Fallo sincrono del worker sin evento del motor (pool caido, etc.)."""
        purge_temporary_files(task.destination_path)
        try:
            task.fail(message)
        except Exception:  # noqa: BLE001
            task.status = DownloadState.FAILED
            task.error_message = message
        self._save(task)
        self._release_slot(task.id.value)
        self.error.emit(task.id.value, message)
        self._dispatch()

    def _handle_cancelled_terminal(self, task_id: str) -> None:
        """Cierra una activa cancelada cuando el motor no publicara evento."""
        entry = self._entry_if_active(task_id)
        if entry is None:
            return
        self._finalize_cancellation(entry.task)
        self._release_slot(task_id)
        self._dispatch()

    # ------------------------------------------------------------ Handlers bus
    def _on_progress_event(self, event: DownloadProgressChangedEvent) -> None:
        if self._entry_if_active(event.task_id) is None:
            return  # progreso de una tarea que la cola ya cerro: ignorar
        self.progress.emit(
            event.task_id,
            float(event.progress_percent),
            float(event.speed_bps),
            format_eta(event.eta_seconds),
            humanize_bytes(event.downloaded_bytes),
            humanize_bytes(event.total_bytes),
        )

    def _on_completed_event(self, event: DownloadCompletedEvent) -> None:
        if self._entry_if_active(event.task_id) is None:
            return
        if event.warning_message:
            self.quality_warning.emit(event.task_id, event.warning_message)
        self._release_slot(event.task_id)
        self.finished.emit(event.task_id, event.destination_path)
        self._dispatch()

    def _on_failed_event(self, event: DownloadFailedEvent) -> None:
        entry = self._entry_if_active(event.task_id)
        if entry is None:
            return
        purge_temporary_files(entry.task.destination_path)
        self._release_slot(event.task_id)
        self.error.emit(event.task_id, event.error_message)
        self._dispatch()

    def _on_cancelled_event(self, event: DownloadCancelledEvent) -> None:
        entry = self._entry_if_active(event.task_id)
        if entry is None:
            return
        purge_temporary_files(entry.task.destination_path)
        try:
            entry.task.cancel()
        except Exception:  # noqa: BLE001
            entry.task.status = DownloadState.CANCELLED
        self._save(entry.task)
        self._release_slot(event.task_id)
        self.cancelled.emit(event.task_id)
        self._dispatch()

    # ------------------------------------------------------------ Infraestructura
    def _publish(self, event: Any) -> None:
        if self._bus is not None:
            try:
                self._bus.publish(event)
            except Exception as ex:  # noqa: BLE001 - el bus jamas rompe la cola
                logger.warning("Fallo publicando %s: %s", type(event).__name__, ex)

    def _save(self, task: DownloadTask) -> None:
        if self._repository is None:
            return
        try:
            self._repository.save(task)
        except Exception as ex:  # noqa: BLE001 - persistencia best-effort
            logger.warning("No se pudo persistir la tarea %s: %s", task.id.value, ex)
