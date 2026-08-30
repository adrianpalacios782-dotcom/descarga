import os
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


class AppTrayIcon(QSystemTrayIcon):
    """Icono interactivo de la bandeja del sistema con notificaciones nativas de Windows."""

    restore_requested = Signal()
    check_updates_requested = Signal()
    exit_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_icon()
        self._setup_menu()
        self.activated.connect(self._on_activated)

    def _setup_icon(self) -> None:
        parent_widget = self.parent()
        if isinstance(parent_widget, QWidget) and not parent_widget.windowIcon().isNull():
            self.setIcon(parent_widget.windowIcon())
        else:
            candidates = [
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "icon.png"),
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "icon.ico"),
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    self.setIcon(QIcon(cand))
                    break

        self.setToolTip("osvaldoDownloaderPro")

    def _setup_menu(self) -> None:
        menu = QMenu()
        menu.setObjectName("TrayMenu")
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #111827;
                color: #F8FAFC;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 8px;
                padding: 6px 4px;
            }
            QMenu::item {
                background-color: transparent;
                color: #F8FAFC;
                padding: 8px 24px 8px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }
            QMenu::item:selected {
                background-color: #1E293B;
                color: #818CF8;
            }
            QMenu::item:disabled {
                color: #64748B;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(255, 255, 255, 0.1);
                margin: 4px 8px;
            }
            """
        )

        act_restore = menu.addAction("Mostrar osvaldoDownloaderPro")
        act_restore.triggered.connect(self.restore_requested.emit)

        menu.addSeparator()

        act_update = menu.addAction("Buscar actualizaciones...")
        act_update.triggered.connect(self.check_updates_requested.emit)

        menu.addSeparator()

        act_exit = menu.addAction("Salir")
        act_exit.triggered.connect(self.exit_requested.emit)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore_requested.emit()

    def notify_download_completed(self, title: str, file_path: str = "") -> None:
        """Emite una notificación nativa de Windows informando la descarga completada."""
        if not self.isVisible():
            return
        msg = f"'{title}' se ha descargado correctamente."
        self.showMessage(
            "Descarga completada",
            msg,
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def notify_download_failed(self, title: str, error: str = "") -> None:
        """Emite una notificación nativa de Windows informando un error de descarga."""
        if not self.isVisible():
            return
        msg = f"Error al descargar '{title}': {error}" if error else f"No se pudo descargar '{title}'."
        self.showMessage(
            "Error de descarga",
            msg,
            QSystemTrayIcon.MessageIcon.Warning,
            6000,
        )
