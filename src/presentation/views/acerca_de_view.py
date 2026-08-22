from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QPushButton

import src as app_pkg


class AcercaDeView(QWidget):
    """Vista con información corporativa, diagnóstico del entorno e integración de FFmpeg."""

    update_check_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Acerca de osvaldoDownloaderPro")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        version_lbl = QLabel(
            f"osvaldoDownloaderPro v{app_pkg.__version__} (Release Principal)"
        )
        version_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #1db954;")

        # Línea explícita de versión requerida en "Acerca de".
        self.lbl_version_line = QLabel(f"Versión: {app_pkg.__version__}")
        self.lbl_version_line.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #b3b3b3;"
        )

        desc_lbl = QLabel(
            "Aplicación de escritorio nativa e independiente para gestionar y descargar contenido "
            "multimedia desde YouTube, TikTok, Instagram y Facebook mediante Arquitectura Hexagonal y Monolito Modular."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 13px; color: #b3b3b3;")

        # Diagnóstico de FFmpeg
        self.lbl_ffmpeg_status = QLabel("Estado de FFmpeg: Verificando...")
        self.lbl_ffmpeg_status.setStyleSheet("font-size: 13px; color: #1db954; font-weight: 600;")

        btn_diagnostics = QPushButton("Exportar Paquete de Diagnóstico (.zip)")
        btn_diagnostics.setObjectName("SecondaryButton")

        btn_check_updates = QPushButton("Buscar actualizaciones")
        btn_check_updates.setObjectName("SecondaryButton")
        btn_check_updates.clicked.connect(self.update_check_requested.emit)

        card_layout.addWidget(version_lbl)
        card_layout.addWidget(self.lbl_version_line)
        card_layout.addWidget(desc_lbl)
        card_layout.addWidget(self.lbl_ffmpeg_status)
        card_layout.addWidget(btn_diagnostics)
        card_layout.addWidget(btn_check_updates)

        layout.addWidget(card)
        layout.addStretch()

    def set_ffmpeg_status(self, available: bool, version: str = "") -> None:
        if available:
            if version:
                self.lbl_ffmpeg_status.setText(f"Estado de FFmpeg: Disponible — versión {version}")
            else:
                self.lbl_ffmpeg_status.setText("Estado de FFmpeg: Disponible y funcional")
            self.lbl_ffmpeg_status.setStyleSheet("font-size: 13px; color: #1db954; font-weight: 700;")
        else:
            self.lbl_ffmpeg_status.setText("Estado de FFmpeg: No detectado (Modo streaming directo)")
            self.lbl_ffmpeg_status.setStyleSheet("font-size: 13px; color: #f59e0b; font-weight: 700;")
