"""Diálogo de actualización integrado con el estilo visual de osvaldoDownloaderPro.

Componente puramente presentacional: la orquestación (consulta, descarga en
hilo worker, verificación y lanzamiento) vive en UpdateCoordinator. Las notas
de la versión se muestran SIEMPRE como texto plano (nunca HTML) para impedir
inyección de contenido remoto.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.application.use_cases.check_for_updates import UpdateCheckResult
from src.presentation.styles.styles import DARK_PALETTE, DARK_STYLE

_COLOR_TEXT_DIM = DARK_PALETTE.text_secondary
_COLOR_ACCENT = DARK_PALETTE.accent
_COLOR_WARNING = DARK_PALETTE.warning


def _format_bytes(num_bytes: float) -> str:
    if num_bytes < 0:
        return "?"
    mb = num_bytes / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    return f"{num_bytes / 1024:.0f} KB"


class UpdateDialog(QDialog):
    """Diálogo "Nueva actualización disponible" con progreso y estados claros."""

    update_accepted = Signal()
    later_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, result: UpdateCheckResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(DARK_STYLE)
        self.setWindowTitle("Actualización de osvaldoDownloaderPro")
        self.setModal(True)
        self.setMinimumWidth(560)

        self._state = "info"  # info | downloading | installing | error

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(14)

        # --- Título -----------------------------------------------------
        title = QLabel("Nueva actualización disponible")
        title.setStyleSheet(
            f"font-size: 19px; font-weight: 800; color: {DARK_PALETTE.text_primary};"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "Hay una nueva versión de osvaldoDownloaderPro lista para instalarse."
        )
        subtitle.setStyleSheet(f"font-size: 13px; color: {_COLOR_TEXT_DIM};")
        layout.addWidget(subtitle)

        # --- Versiones (tarjeta integrada) -------------------------------
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        row_current = QHBoxLayout()
        lbl_cur = QLabel("Versión actual:")
        lbl_cur.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {DARK_PALETTE.text_secondary};")
        val_cur = QLabel(str(result.current_version))
        val_cur.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {DARK_PALETTE.text_primary};")
        row_current.addWidget(lbl_cur)
        row_current.addWidget(val_cur)
        row_current.addStretch()
        card_layout.addLayout(row_current)

        row_new = QHBoxLayout()
        lbl_new = QLabel("Nueva versión:")
        lbl_new.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {DARK_PALETTE.text_secondary};")
        val_new = QLabel(str(result.latest_version))
        val_new.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {_COLOR_ACCENT};"
        )
        row_new.addWidget(lbl_new)
        row_new.addWidget(val_new)
        row_new.addStretch()
        card_layout.addLayout(row_new)

        layout.addWidget(card)

        # --- Novedades ----------------------------------------------------
        notes = (result.release.release_notes or "").strip() if result.release else ""
        if notes:
            notes_title = QLabel("Novedades de esta versión")
            notes_title.setStyleSheet(
                f"font-size: 13px; font-weight: 700; color: {DARK_PALETTE.text_secondary};"
            )
            layout.addWidget(notes_title)

            notes_label = QLabel(notes[:8000])
            notes_label.setTextFormat(Qt.TextFormat.PlainText)
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet(
                f"font-size: 13px; color: {DARK_PALETTE.text_primary};"
            )

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(notes_label)
            scroll.setMaximumHeight(150)
            layout.addWidget(scroll)

        # --- Progreso + estado ---------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size: 12px; color: {_COLOR_TEXT_DIM};")
        self.status_label.setVisible(False)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # --- Botones ---------------------------------------------------------
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        self.btn_later = QPushButton("Más tarde")
        self.btn_later.setObjectName("SecondaryButton")
        self.btn_update = QPushButton("Actualizar ahora")
        self.btn_update.setObjectName("PrimaryButton")
        buttons_row.addWidget(self.btn_later)
        buttons_row.addWidget(self.btn_update)
        layout.addLayout(buttons_row)

        self.btn_update.clicked.connect(self._on_update_clicked)
        self.btn_later.clicked.connect(self._on_later_clicked)

    # ------------------------------------------------------------ Intents
    def _on_update_clicked(self) -> None:
        if self._state != "info":
            return
        self._state = "downloading"
        self.update_accepted.emit()
        self.btn_update.setEnabled(False)
        self.btn_later.setText("Cancelar")
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.set_status("Preparando descarga…")

    def _on_later_clicked(self) -> None:
        if self._state == "downloading":
            self.cancel_requested.emit()
            self.reject()
            return
        self.later_requested.emit()
        self.reject()

    # ------------------------------------------------------------- Slots
    def on_download_progress(self, downloaded: int, total: int) -> None:
        if self._state != "downloading":
            return
        if total and total > 0:
            pct = min(100, int(downloaded * 100 / total))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(pct)
            self.set_status(
                f"Descargando… {pct}% "
                f"({_format_bytes(downloaded)} de {_format_bytes(total)})"
            )
        else:
            self.progress_bar.setRange(0, 0)  # indeterminado
            self.set_status(f"Descargando… {_format_bytes(downloaded)}")

    def set_status(self, text: str, is_error: bool = False) -> None:
        color = _COLOR_WARNING if is_error else _COLOR_TEXT_DIM
        self.status_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {color};")
        self.status_label.setText(text)

    def on_verification_started(self) -> None:
        if self._state == "downloading":
            self.progress_bar.setValue(100)
            self.set_status("Verificando integridad del instalador (SHA-256)…")

    def on_ready_to_install(self) -> None:
        self._state = "installing"
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.btn_later.setEnabled(False)
        self.btn_update.setEnabled(False)
        self.set_status(
            "Verificación completada. Iniciando el instalador… "
            "osvaldoDownloaderPro se cerrará y se abrirá con la nueva versión."
        )

    def on_download_error(self, message: str) -> None:
        """Muestra un error claro y permite continuar usando la versión actual."""
        was_downloading = self._state == "downloading"
        self._state = "error"
        self.progress_bar.setVisible(False)
        if was_downloading:
            try:
                self.btn_later.clicked.disconnect(self._on_later_clicked)
            except (RuntimeError, TypeError):
                pass
            self.btn_later.clicked.connect(self.reject)
        self.btn_later.setText("Continuar con la versión actual")
        self.btn_later.setEnabled(True)
        self.btn_update.setVisible(False)
        self.set_status(message, is_error=True)
