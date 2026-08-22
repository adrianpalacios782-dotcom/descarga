"""Coordinador del sistema de actualización (capa de presentación).

Orquesta: consulta inicial → diálogo → descarga en hilo worker → verificación
SHA-256 en disco → lanzamiento silencioso del instalador + reinicio.

Garantías:
- NUNCA bloquea el hilo de la UI: toda E/S de red ocurre en hilos daemon.
- Una falla del actualizador jamás impide usar la aplicación: los errores se
  notifican por señales y la app continúa.
- Los archivos temporales se limpian siempre (éxito, fallo o cancelación);
  el directorio post-lanzamiento lo elimina la cadena cmd del propio launcher
  y, como red de seguridad, cleanup_stale_update_dirs al arrancar.
"""
import logging
import threading

from PySide6.QtCore import QObject, Signal

from src.application.use_cases.check_for_updates import (
    CheckForUpdatesUseCase,
    UpdateCheckResult,
)
from src.infrastructure.updater.github_releases_source import GitHubReleasesSource
from src.infrastructure.updater.installer_downloader import InstallerDownloader
from src.infrastructure.updater.installer_launcher import (
    InstallerLauncher,
    cleanup_stale_update_dirs,
    cleanup_temp_dir,
    make_update_tempdir,
)

logger = logging.getLogger(__name__)


class UpdateCoordinator(QObject):
    """Controlador no bloqueante de comprobación/descarga/instalación."""

    # result: UpdateCheckResult | None (None = fallo de consulta), manual
    check_finished = Signal(object, bool)
    download_progress = Signal(int, int)
    download_status = Signal(str)
    ready_to_install = Signal()
    install_started = Signal()
    update_failed = Signal(str)   # mensaje claro para la UI
    update_cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._check_use_case = CheckForUpdatesUseCase(update_source=GitHubReleasesSource())
        self._downloader = InstallerDownloader()
        self._launcher = InstallerLauncher()

        self._checking = False
        self._updating = False
        self._cancel_event = threading.Event()
        self._temp_dir = None

    # ------------------------------------------------------------ Consulta
    def check_for_updates(self, manual: bool = False) -> None:
        """Comprueba una vez la fuente oficial. Seguro de llamar al inicio."""
        if self._checking or self._updating:
            return
        self._checking = True
        worker = threading.Thread(target=self._check_worker, args=(manual,), daemon=True)
        worker.start()

    def _check_worker(self, manual: bool) -> None:
        # Red de seguridad: restos de actualizaciones anteriores abandonadas.
        try:
            cleanup_stale_update_dirs()
        except Exception:  # noqa: BLE001 - best-effort, jamás bloquea
            pass
        try:
            result = self._check_use_case.execute(self._current_app_version())
            logger.info(
                "Actualización: chequeo completado (estado=%s).",
                result.status.value,
            )
            self.check_finished.emit(result, manual)
        except Exception as exc:  # noqa: BLE001 - una falla NUNCA rompe la app
            logger.warning("Actualización: consulta fallida (%s).", exc.__class__.__name__)
            self.check_finished.emit(None, manual)
        finally:
            self._checking = False

    @staticmethod
    def _current_app_version() -> str:
        import src as app_pkg

        return app_pkg.__version__

    # ------------------------------------------------------------ Descarga
    def begin_update(self, result: UpdateCheckResult) -> None:
        """Inicia descarga+verificación+instalación tras aceptar el usuario."""
        if self._updating or result is None or result.release is None:
            return
        asset = result.release.installer_asset
        if asset is None:
            self.update_failed.emit(
                "El release publicado no incluye un instalador para Windows."
            )
            return

        self._updating = True
        self._cancel_event.clear()
        try:
            self._temp_dir = make_update_tempdir()
        except OSError:
            self._updating = False
            self.update_failed.emit("No se pudo crear el directorio temporal.")
            return

        worker = threading.Thread(
            target=self._download_worker,
            args=(asset,),
            daemon=True,
        )
        worker.start()

    def _download_worker(self, asset) -> None:  # type: ignore[no-untyped-def]
        temp_dir = self._temp_dir
        installer_path = None
        try:
            self.download_status.emit("Descargando actualización…")
            installer_path = self._downloader.download_to_tempdir(
                asset=asset,
                temp_dir=temp_dir,
                progress_callback=lambda d, t: self.download_progress.emit(d, t),
                cancel_event=self._cancel_event,
            )

            if self._cancel_event.is_set():
                raise InterruptedError("Cancelada por el usuario.")

            self.download_status.emit("Verificando integridad (SHA-256)…")
            # Re-verificación EN DISCO antes de ejecutar (defensa en profundidad).
            self._launcher.verify_installer_file(installer_path, asset)
            self.download_progress.emit(100, 100)
            self.ready_to_install.emit()

            self.install_started.emit()
            self._launcher.install_and_restart(installer_path, asset)
            # La cadena cmd del launcher borra este temp dir tras instalar.
            self._temp_dir = None
            logger.info("Actualización: instalador lanzado correctamente.")

        except InterruptedError:
            cleanup_temp_dir(temp_dir)
            self._temp_dir = None
            self.update_cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            cleanup_temp_dir(temp_dir)
            self._temp_dir = None
            logger.warning("Actualización: proceso fallido (%s).", exc.__class__.__name__)
            message = str(exc) or "Error inesperado durante la actualización."
            self.update_failed.emit(message)
        finally:
            self._updating = False

    # ---------------------------------------------------------- Cancelación
    def request_cancel(self) -> None:
        """Solicita abortar la descarga en curso; el worker limpia temporales."""
        self._cancel_event.set()

    @property
    def is_busy(self) -> bool:
        return self._checking or self._updating
