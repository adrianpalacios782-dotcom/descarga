from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
)

import src as app_pkg
from src.presentation.styles.theme import get_current_palette


class AcercaDeView(QWidget):
    """Vista con información corporativa, diagnóstico del entorno e integración de FFmpeg y yt-dlp."""

    update_check_requested = Signal()
    engine_update_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Acerca de")
        title.setObjectName("ViewTitle")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(16)

        logo = QLabel()
        logo.setPixmap(AcercaDeView._build_logo_pixmap())
        logo.setFixedSize(64, 64)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(logo, alignment=Qt.AlignmentFlag.AlignTop)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(4)
        name_lbl = QLabel("osvaldoDownloaderPro")
        name_lbl.setObjectName("AboutAppName")
        tagline = QLabel("Gestor de descargas multimedia")
        tagline.setObjectName("ViewSubtitle")
        release_lbl = QLabel(
            f"osvaldoDownloaderPro v{app_pkg.__version__} (Release Principal)"
        )
        release_lbl.setObjectName("AboutAppRelease")

        # Línea explícita de versión requerida en "Acerca de".
        self.lbl_version_line = QLabel(f"Versión: {app_pkg.__version__}")
        self.lbl_version_line.setObjectName("AboutAppVersion")

        brand_col.addWidget(name_lbl)
        brand_col.addWidget(tagline)
        brand_col.addWidget(release_lbl)
        brand_col.addWidget(self.lbl_version_line)
        brand_row.addLayout(brand_col, stretch=1)
        card_layout.addLayout(brand_row)

        desc_lbl = QLabel(
            "Aplicación de escritorio nativa e independiente para gestionar y descargar contenido "
            "multimedia desde YouTube, TikTok, Instagram, Facebook, Twitch, Kick y cualquier sitio web "
            "mediante Arquitectura Hexagonal y Monolito Modular."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setObjectName("HintLabel")

        # Diagnóstico de FFmpeg
        self.lbl_ffmpeg_status = QLabel("Estado de FFmpeg: Verificando...")
        self.lbl_ffmpeg_status.setObjectName("AboutStatusSuccess")

        # Diagnóstico del Motor yt-dlp
        self.lbl_engine_status = QLabel("Motor yt-dlp: Verificando versión...")
        self.lbl_engine_status.setObjectName("AboutStatusSuccess")

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        btn_diagnostics = QPushButton("Exportar Paquete de Diagnóstico (.zip)")
        btn_diagnostics.setObjectName("SecondaryButton")

        btn_update_engine = QPushButton("⚡ Actualizar Motor yt-dlp")
        btn_update_engine.setObjectName("SecondaryButton")
        btn_update_engine.clicked.connect(self.engine_update_requested.emit)

        btn_check_updates = QPushButton("Buscar actualizaciones")
        btn_check_updates.setObjectName("PrimaryButton")
        btn_check_updates.clicked.connect(self.update_check_requested.emit)

        buttons_row.addWidget(btn_diagnostics)
        buttons_row.addWidget(btn_update_engine)
        buttons_row.addWidget(btn_check_updates)
        buttons_row.addStretch()

        card_layout.addWidget(desc_lbl)
        card_layout.addWidget(self.lbl_ffmpeg_status)
        card_layout.addWidget(self.lbl_engine_status)
        card_layout.addSpacing(6)
        card_layout.addLayout(buttons_row)

        layout.addWidget(card)
        layout.addStretch()

    @staticmethod
    def _build_logo_pixmap(size: int = 64) -> QPixmap:
        """Logotipo vectorial: cuadrado redondeado verde con flecha de descarga."""
        palette = get_current_palette()
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.accent))
        radius = int(size * 0.24)
        painter.drawRoundedRect(0, 0, size, size, radius, radius)

        pen_color = QColor(palette.text_on_accent)
        stroke = max(2.0, size * 0.055)
        pen = painter.pen()
        pen.setColor(pen_color)
        pen.setWidthF(stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        s = size / 64.0
        cx = 32.0 * s
        painter.drawLine(int(cx), int(18 * s), int(cx), int(38 * s))
        painter.drawLine(int(23 * s), int(30 * s), int(cx), int(39 * s))
        painter.drawLine(int(41 * s), int(30 * s), int(cx), int(39 * s))
        tray_y = 46 * s
        painter.drawLine(int(20 * s), int(tray_y), int(20 * s), int(50 * s))
        painter.drawLine(int(20 * s), int(50 * s), int(44 * s), int(50 * s))
        painter.drawLine(int(44 * s), int(50 * s), int(44 * s), int(tray_y))
        painter.end()
        return pixmap

    def set_ffmpeg_status(self, available: bool, version: str = "") -> None:
        if available:
            if version:
                self.lbl_ffmpeg_status.setText(f"Estado de FFmpeg: Disponible — versión {version}")
            else:
                self.lbl_ffmpeg_status.setText("Estado de FFmpeg: Disponible y funcional")
            self.lbl_ffmpeg_status.setObjectName("AboutStatusSuccess")
        else:
            self.lbl_ffmpeg_status.setText("Estado de FFmpeg: No detectado (Modo streaming directo)")
            self.lbl_ffmpeg_status.setObjectName("AboutStatusWarning")
        self.lbl_ffmpeg_status.style().unpolish(self.lbl_ffmpeg_status)
        self.lbl_ffmpeg_status.style().polish(self.lbl_ffmpeg_status)

    def set_engine_status(self, version: str, is_custom: bool = False) -> None:
        if version:
            tag = " (actualizado en AppData)" if is_custom else " (empaquetado)"
            self.lbl_engine_status.setText(f"Motor yt-dlp: v{version}{tag}")
            self.lbl_engine_status.setObjectName("AboutStatusSuccess")
        else:
            self.lbl_engine_status.setText("Motor yt-dlp: No detectado")
            self.lbl_engine_status.setObjectName("AboutStatusWarning")
        self.lbl_engine_status.style().unpolish(self.lbl_engine_status)
        self.lbl_engine_status.style().polish(self.lbl_engine_status)

