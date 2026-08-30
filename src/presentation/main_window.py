import logging
import sys
import threading
from typing import Any

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.favorite_item import FavoriteItem
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.ports.favorite_repository import IFavoriteRepository
from src.presentation.components.sidebar import SidebarWidget
from src.presentation.components.system_tray import AppTrayIcon
from src.presentation.components.title_bar import TitleBar
from src.presentation.components.update_dialog import UpdateDialog
from src.presentation.styles.styles import DARK_STYLE
from src.presentation.view_models.main_view_model import MainViewModel
from src.presentation.view_models.update_coordinator import UpdateCoordinator
from src.presentation.views import (
    InicioView,
    DescargasView,
    HistorialView,
    FavoritosView,
    ConfiguracionView,
    AcercaDeView,
)

logger = logging.getLogger(__name__)

# Retraso del primer chequeo de actualizaciones: deja respirar al arranque y
# evita competir con la inicialización pesada (SQLite, FFmpeg, yt-dlp).
STARTUP_UPDATE_CHECK_DELAY_MS = 2000

# Zonas de redimensionado nativas de Windows (WM_NCHITTEST).
_HT_CAPTION = 2
_HT_LEFT = 10
_HT_RIGHT = 11
_HT_TOP = 12
_HT_TOPLEFT = 13
_HT_TOPRIGHT = 14
_HT_BOTTOM = 15
_HT_BOTTOMLEFT = 16
_HT_BOTTOMRIGHT = 17
_RESIZE_MARGIN = 6


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación osvaldoDownloaderPro."""

    ffmpeg_status_checked = Signal(bool, str)

    def __init__(
        self,
        view_model: MainViewModel,
        favorite_repository: IFavoriteRepository | None = None,
    ) -> None:
        super().__init__()
        self.view_model = view_model
        self.favorite_repo = favorite_repository

        self.setWindowTitle("osvaldoDownloaderPro")
        self.resize(1160, 720)
        # Mínimo pensado para que la previsualización completa quepa sin cortes
        # en el escenario más pequeño soportado (portátiles 1366x768).
        self.setMinimumSize(980, 700)
        self.setStyleSheet(DARK_STYLE)

        # Barra de título personalizada: ventana frameless con controles
        # propios. El arrastre/snap lo gestiona Windows vía WM_NCHITTEST.
        self._apply_frameless()

        # Estructura raíz: barra de título + contenido (sidebar | vistas)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._title_bar = TitleBar()
        self._title_bar.minimize_requested.connect(self.showMinimized)
        self._title_bar.maximize_toggle_requested.connect(self._toggle_maximize)
        self._title_bar.close_requested.connect(self.close)
        root_layout.addWidget(self._title_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        root_layout.addLayout(content_layout, stretch=1)

        # Sidebar
        self.sidebar = SidebarWidget()
        content_layout.addWidget(self.sidebar)

        # Stacked Views
        self.stacked = QStackedWidget()

        self.inicio_view = InicioView()
        self.descargas_view = DescargasView()
        self.historial_view = HistorialView()
        self.favoritos_view = FavoritosView()
        self.configuracion_view = ConfiguracionView(
            settings_repo=getattr(self.view_model, "settings_repository", None)
        )
        self.acerca_de_view = AcercaDeView()

        self.stacked.addWidget(self.inicio_view)
        self.stacked.addWidget(self.descargas_view)
        self.stacked.addWidget(self.historial_view)
        self.stacked.addWidget(self.favoritos_view)
        self.stacked.addWidget(self.configuracion_view)
        self.stacked.addWidget(self.acerca_de_view)

        content_layout.addWidget(self.stacked, stretch=1)

        # Conectar Sidebar con StackedWidget
        self.sidebar.nav_changed.connect(self.stacked.setCurrentIndex)
        self.sidebar.nav_changed.connect(self._on_tab_changed)

        # Preferencia de animaciones (Apariencia) -> microinteracciones Inicio
        if hasattr(self.configuracion_view, "animations_enabled_changed"):
            self.configuracion_view.animations_enabled_changed.connect(
                self.inicio_view.set_animations_enabled
            )

        # Conectar Signals del ViewModel
        self._connect_signals()

        # Sistema de actualización (no bloqueante)
        self.update_coordinator = UpdateCoordinator(parent=self)
        self._update_dialog: UpdateDialog | None = None
        self._connect_update_signals()

        # Preferencias y soporte de System Tray
        settings_repo = getattr(self.view_model, "settings_repository", None)
        self._minimize_to_tray: bool = bool(settings_repo.get("minimize_to_tray", False)) if settings_repo else False
        self._tray_notifications: bool = bool(settings_repo.get("tray_notifications", True)) if settings_repo else True
        self._is_quitting_from_tray: bool = False
        self._tray_balloon_shown: bool = False

        self.tray_icon = AppTrayIcon(self)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
        self._setup_tray_signals()

    def _apply_frameless(self) -> None:
        """Activa el modo frameless solo si es estable en esta plataforma."""
        try:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        except Exception:  # pragma: no cover - plataformas atípicas
            logger.warning("No se pudo activar la barra de título personalizada.")

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (API Qt)
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            title_bar = getattr(self, "_title_bar", None)
            if title_bar is not None:
                title_bar.refresh_window_state_icon(self.isMaximized())

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (API Qt)
        """Minimiza a la bandeja del sistema si la opción está activa."""
        if self._minimize_to_tray and not self._is_quitting_from_tray and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_balloon_shown:
                self.tray_icon.showMessage(
                    "osvaldoDownloaderPro",
                    "La aplicación continúa ejecutándose en segundo plano.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
                self._tray_balloon_shown = True
        else:
            super().closeEvent(event)

    # ------------------------------------------- Redimensionado nativo
    def nativeEvent(self, event_type: Any, message: Any) -> Any:  # noqa: N802 (API Qt)
        """WM_NCHITTEST: bordes redimensionables y arrastre sobre la barra."""
        handled = self._handle_nc_hit_test(event_type, message)
        if handled is not None:
            return handled
        return super().nativeEvent(event_type, message)

    def _handle_nc_hit_test(self, event_type: Any, message: Any) -> tuple[bool, int] | None:
        if sys.platform != "win32" or event_type != "windows_generic_MSG":
            return None
        try:
            import ctypes.wintypes as wintypes

            msg = wintypes.MSG.from_address(int(message))
            if msg.message != 0x0084:  # WM_NCHITTEST
                return None
            from PySide6.QtGui import QCursor

            pos = self.mapFromGlobal(QCursor.pos())
            width, height = self.width(), self.height()

            if not self.isMaximized():
                near_left = pos.x() < _RESIZE_MARGIN
                near_right = pos.x() > width - _RESIZE_MARGIN
                near_top = pos.y() < _RESIZE_MARGIN
                near_bottom = pos.y() > height - _RESIZE_MARGIN
                if near_top and near_left:
                    return True, _HT_TOPLEFT
                if near_top and near_right:
                    return True, _HT_TOPRIGHT
                if near_bottom and near_left:
                    return True, _HT_BOTTOMLEFT
                if near_bottom and near_right:
                    return True, _HT_BOTTOMRIGHT
                if near_left:
                    return True, _HT_LEFT
                if near_right:
                    return True, _HT_RIGHT
                if near_top:
                    return True, _HT_TOP
                if near_bottom:
                    return True, _HT_BOTTOM

            title_bar = getattr(self, "_title_bar", None)
            if title_bar is not None and title_bar.isVisible():
                local = title_bar.mapFrom(self, pos)
                if 0 <= local.x() <= title_bar.width() and 0 <= local.y() <= title_bar.height():
                    if not title_bar.is_drag_zone(local):
                        return None
                    return True, _HT_CAPTION
        except Exception:  # pragma: no cover - nunca romper por el hit-test
            logger.debug("WM_NCHITTEST no gestionado", exc_info=True)
        return None

    def _connect_signals(self) -> None:
        # InicioView -> ViewModel
        self.inicio_view.analyze_requested.connect(self.view_model.analyze_url)
        self.inicio_view.download_requested.connect(self._on_download_requested)
        self.inicio_view.batch_requested.connect(self._open_batch_download_dialog)

        # ViewModel -> InicioView
        self.view_model.analysis_started.connect(lambda: self.inicio_view.set_analyzing_state(True))
        self.view_model.media_analyzed.connect(self.inicio_view.set_metadata)
        self.view_model.media_analyzed.connect(self._on_media_analyzed)
        self.view_model.analysis_failed.connect(self.inicio_view.show_error)

        # ViewModel -> DescargasView
        self.view_model.download_created.connect(self.descargas_view.add_task)
        self.view_model.download_queued.connect(
            lambda task_id: self.descargas_view.set_state(task_id, "QUEUED")
        )
        self.view_model.download_started.connect(
            lambda task_id: self.descargas_view.set_state(task_id, "DOWNLOADING")
        )
        self.view_model.download_progress.connect(self.descargas_view.update_progress)
        self.view_model.download_state_changed.connect(self.descargas_view.set_state)
        self.view_model.download_quality_warning.connect(
            self.descargas_view.show_quality_warning
        )

        # DescargasView -> ViewModel
        self.descargas_view.pause_requested.connect(self.view_model.pause_download)
        self.descargas_view.resume_requested.connect(self.view_model.resume_download)
        self.descargas_view.cancel_requested.connect(self.view_model.cancel_download)
        self.descargas_view.retry_requested.connect(self.view_model.retry_download)

        # DescargasView -> acciones del explorador de Windows
        self.descargas_view.open_file_requested.connect(self._open_in_explorer)
        self.descargas_view.open_folder_requested.connect(self._open_folder)

        # Diagnóstico FFmpeg -> AcercaDeView (emisión thread-safe)
        self.ffmpeg_status_checked.connect(self.acerca_de_view.set_ffmpeg_status)

        # ConfiguracionView -> ViewModel / InicioView
        self.configuracion_view.settings_saved.connect(self._on_settings_saved)

        # HistorialView -> acciones interactivas
        self.historial_view.open_file_requested.connect(self._open_file)
        self.historial_view.open_folder_requested.connect(self._open_in_explorer)
        self.historial_view.redownload_requested.connect(self._on_redownload_from_history)
        self.historial_view.delete_task_requested.connect(self._on_delete_from_history)

        # FavoritosView -> acciones interactivas
        self.favoritos_view.download_requested.connect(self._on_redownload_from_history)
        self.favoritos_view.remove_requested.connect(self._on_remove_favorite)
        self.inicio_view.preview_card.favorite_toggled.connect(self._on_favorite_toggled_in_preview)

        # ViewModel -> Notificaciones en System Tray
        self.view_model.download_completed.connect(self._on_tray_download_completed)
        self.view_model.download_failed.connect(self._on_tray_download_failed)
        self.view_model.batch_completed.connect(self._on_batch_completed)

    def _on_settings_saved(self, settings: dict[str, Any]) -> None:
        """Aplica las preferencias guardadas a la lógica de negocio y vistas dependientes."""
        self.view_model.apply_settings(settings)
        default_dir = settings.get("default_download_dir")
        if default_dir:
            self.inicio_view.set_default_download_dir(str(default_dir))
        if "minimize_to_tray" in settings:
            self._minimize_to_tray = bool(settings["minimize_to_tray"])
        if "tray_notifications" in settings:
            self._tray_notifications = bool(settings["tray_notifications"])

    def _connect_update_signals(self) -> None:
        # Vistas manuales -> coordinador (con feedback visible)
        self.configuracion_view.update_check_requested.connect(
            lambda: self.update_coordinator.check_for_updates(manual=True)
        )
        self.acerca_de_view.update_check_requested.connect(
            lambda: self.update_coordinator.check_for_updates(manual=True)
        )

        # Coordinador -> UI
        self.update_coordinator.check_finished.connect(self._on_update_check_finished)
        self.update_coordinator.download_progress.connect(self._on_download_progress)
        self.update_coordinator.download_status.connect(self._on_download_status)
        self.update_coordinator.ready_to_install.connect(self._on_ready_to_install)
        self.update_coordinator.install_started.connect(self._on_install_started)
        self.update_coordinator.update_failed.connect(self._on_update_failed)
        self.update_coordinator.update_cancelled.connect(self._close_update_dialog)

    # ------------------------------------------------- Actualizaciones
    def schedule_startup_update_check(self) -> None:
        """Chequeo ÚNICO al iniciar; cualquier falla es silenciosa."""
        QTimer.singleShot(
            STARTUP_UPDATE_CHECK_DELAY_MS,
            self.update_coordinator.check_for_updates,
        )

    def _on_update_check_finished(self, result: Any, manual: bool) -> None:
        if result is None:
            if manual:
                QMessageBox.warning(
                    self,
                    "Actualizaciones",
                    "No se pudo comprobar si hay actualizaciones.\n\n"
                    "Comprueba tu conexión a Internet e inténtalo de nuevo. "
                    "Puedes seguir usando la aplicación con normalidad.",
                )
            return  # fallo en chequeo automático de inicio: silencio total.
        if not result.update_available:
            if manual:
                QMessageBox.information(
                    self,
                    "Actualizaciones",
                    f"Ya estás usando la última versión "
                    f"(v{result.current_version}).",
                )
            return  # al día o downgrade bloqueado: nada que mostrar.
        if result.release is None or result.release.installer_asset is None:
            logger.info("Actualización disponible pero sin instalador Windows; se ignora.")
            return
        if self._update_dialog is not None and self._update_dialog.isVisible():
            return
        self._open_update_dialog(result)

    def _open_update_dialog(self, result: Any) -> None:
        dialog = UpdateDialog(result, parent=self)
        dialog.update_accepted.connect(lambda: self.update_coordinator.begin_update(result))
        dialog.later_requested.connect(dialog.reject)
        dialog.cancel_requested.connect(self.update_coordinator.request_cancel)
        self._update_dialog = dialog
        dialog.exec()

    def _close_update_dialog(self) -> None:
        if self._update_dialog is not None:
            self._update_dialog.reject()
            self._update_dialog = None

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        if self._update_dialog is not None:
            self._update_dialog.on_download_progress(downloaded, total)

    def _on_download_status(self, text: str) -> None:
        if self._update_dialog is not None:
            self._update_dialog.set_status(text)

    def _on_ready_to_install(self) -> None:
        if self._update_dialog is not None:
            self._update_dialog.on_ready_to_install()

    def _on_install_started(self) -> None:
        """El instalador verificado ya fue lanzado: cerrar esta aplicación."""
        logger.info("Actualización: cerrando la aplicación para completar la instalación.")
        self.close()
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_update_failed(self, message: str) -> None:
        """Fallo de actualización: mensaje claro y la app sigue funcionando."""
        if self._update_dialog is not None and self._update_dialog.isVisible():
            self._update_dialog.on_download_error(message)
        else:
            QMessageBox.warning(
                self,
                "Actualización",
                f"No se pudo completar la actualización:\n\n{message}\n\n"
                "Puedes seguir usando la versión actual.",
            )

    def _on_download_requested(self, media: MediaMetadata, format_id: str, dest_path: str) -> None:
        sub_cfg = self.inicio_view.preview_card.get_subtitle_config()
        self.view_model.create_and_start_download(media, format_id, dest_path, subtitle_config=sub_cfg)
        self.sidebar.button_group.button(1).setChecked(True)
        self.stacked.setCurrentIndex(1)

    def _open_batch_download_dialog(self) -> None:
        """Abre el diálogo modal de descarga masiva por lotes."""
        from src.presentation.components.batch_download_dialog import BatchDownloadDialog
        default_dir = self.inicio_view.download_config.get_destination_directory() or ""
        dlg = BatchDownloadDialog(default_dir=default_dir, parent=self)
        dlg.batch_requested.connect(self._on_start_batch_download)
        dlg.exec()

    def _on_start_batch_download(self, urls: list[str], quality: str, dest_dir: str) -> None:
        """Cambia a la pestaña de descargas y despacha el procesamiento en lote."""
        self.sidebar.button_group.button(1).setChecked(True)
        self.stacked.setCurrentIndex(1)
        self.view_model.process_batch_downloads(urls, quality, dest_dir)

    def _on_batch_completed(self, success_count: int, fail_count: int) -> None:
        """Emite notificación al finalizar el procesamiento de un lote."""
        if self.tray_icon.isVisible() and self._tray_notifications:
            msg = f"{success_count} descargas encoladas exitosamente."
            if fail_count > 0:
                msg += f" ({fail_count} enlaces con error u omitidos)"
            self.tray_icon.showMessage(
                "Lote de descargas procesado",
                msg,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    @staticmethod
    def _open_file(file_path: str) -> None:
        import os
        import subprocess
        try:
            if os.path.isfile(file_path):
                if sys.platform == "win32":
                    os.startfile(os.path.normpath(file_path))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", file_path])
                else:
                    subprocess.Popen(["xdg-open", file_path])
            else:
                QMessageBox.warning(None, "Archivo", "El archivo no se encuentra en la ruta esperada.")
        except Exception as ex:
            logger.error("No se pudo abrir/reproducir el archivo '%s': %s", file_path, ex)

    @staticmethod
    def _open_in_explorer(file_path: str) -> None:
        import os
        import subprocess
        try:
            if os.path.isfile(file_path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(file_path)])
            else:
                QMessageBox.warning(None, "Archivo", "El archivo no se encuentra en la ruta esperada.")
        except OSError as ex:
            logger.error("No se pudo abrir el explorador para '%s': %s", file_path, ex)

    @staticmethod
    def _open_folder(folder_path: str) -> None:
        import os
        import subprocess
        folder = os.path.dirname(os.path.normpath(folder_path)) if os.path.isfile(folder_path) else folder_path
        try:
            if os.path.isdir(folder):
                subprocess.Popen(["explorer", os.path.normpath(folder)])
            else:
                QMessageBox.warning(None, "Carpeta", "La carpeta de destino no existe.")
        except OSError as ex:
            logger.error("No se pudo abrir la carpeta '%s': %s", folder, ex)

    def _on_tab_changed(self, index: int) -> None:
        if index == 2:  # Historial
            tasks = self.view_model.get_all_tasks()
            self.historial_view.load_history(tasks)
        elif index == 3:  # Favoritos
            if self.favorite_repo is not None:
                favs = self.favorite_repo.get_all()
                self.favoritos_view.load_favorites(favs)
        elif index == 5:  # Acerca de
            self._check_ffmpeg_status()

    def _on_media_analyzed(self, media: MediaMetadata) -> None:
        """Sincroniza el estado del botón favorito al terminar el análisis."""
        if self.favorite_repo is not None:
            url_str = media.url.value if hasattr(media, "url") else str(getattr(media, "original_url", ""))
            is_fav = self.favorite_repo.exists(url_str)
            self.inicio_view.preview_card.set_is_favorite(is_fav)

    def _on_favorite_toggled_in_preview(self, is_fav: bool) -> None:
        """Guarda o remueve el contenido analizado de la base de datos de favoritos."""
        if self.favorite_repo is None or self.inicio_view.current_metadata is None:
            return
        media = self.inicio_view.current_metadata
        url_val = media.url.value if hasattr(media, "url") else str(getattr(media, "original_url", ""))
        if is_fav:
            fav = FavoriteItem(
                url=url_val,
                title=media.title,
                author=media.author or "",
                platform=media.platform or "",
                duration_seconds=media.duration_seconds,
                thumbnail_url=media.thumbnail_url or "",
            )
            self.favorite_repo.add(fav)
        else:
            self.favorite_repo.remove(url_val)

    def _on_remove_favorite(self, url_str: str) -> None:
        """Elimina un favorito y actualiza la lista y el botón de previsualización."""
        if self.favorite_repo is not None:
            self.favorite_repo.remove(url_str)
            favs = self.favorite_repo.get_all()
            self.favoritos_view.load_favorites(favs)
            if self.inicio_view.current_metadata is not None:
                cur_url = self.inicio_view.current_metadata.url.value
                if cur_url == url_str:
                    self.inicio_view.preview_card.set_is_favorite(False)

    def _on_redownload_from_history(self, url_str: str) -> None:
        """Carga la URL del historial en Inicio e inicia el análisis."""
        self.sidebar.button_group.button(0).setChecked(True)
        self.stacked.setCurrentIndex(0)
        self.inicio_view.url_input.setText(url_str)
        self.inicio_view.analyze_requested.emit(url_str)

    def _on_delete_from_history(self, task_id: str) -> None:
        """Elimina la tarea del historial y refresca la vista."""
        if self.view_model.delete_task(task_id):
            tasks = self.view_model.get_all_tasks()
            self.historial_view.load_history(tasks)

    # --------------------------------------------------- Acciones de Bandeja
    def _setup_tray_signals(self) -> None:
        self.tray_icon.restore_requested.connect(self._restore_from_tray)
        self.tray_icon.check_updates_requested.connect(
            lambda: self.update_coordinator.check_for_updates(manual=True)
        )
        self.tray_icon.exit_requested.connect(self._quit_application)

    def _restore_from_tray(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

    def _quit_application(self) -> None:
        self._is_quitting_from_tray = True
        self.close()
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_tray_download_completed(self, task_id: str, dest_path: str) -> None:
        if not self._tray_notifications:
            return
        import os
        title = os.path.basename(dest_path) if dest_path else task_id
        self.tray_icon.notify_download_completed(title, dest_path)

    def _on_tray_download_failed(self, task_id: str, error_msg: str) -> None:
        if not self._tray_notifications:
            return
        self.tray_icon.notify_download_failed(task_id, error_msg)

    def _check_ffmpeg_status(self) -> None:
        def _worker() -> None:
            from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
            adapter = FFmpegProcessAdapter()
            ok, version = adapter.check_availability_sync()
            self.ffmpeg_status_checked.emit(ok, version)

        threading.Thread(target=_worker, daemon=True).start()
