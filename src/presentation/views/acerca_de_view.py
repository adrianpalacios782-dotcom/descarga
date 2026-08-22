from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
)

import src as app_pkg
from src.presentation.styles.styles import DARK_PALETTE


class AcercaDeView(QWidget):
    """Vista con información corporativa, diagnóstico del entorno e integración de FFmpeg."""

    update_check_requested = Signal()

    def __init__(self, parent=None) -> None:
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
        name_lbl.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {DARK_PALETTE.text_primary};"
        )
        tagline = QLabel("Gestor de descargas multimedia")
        tagline.setObjectName("ViewSubtitle")
        release_lbl = QLabel(
            f"osvaldoDownloaderPro v{app_pkg.__version__} (Release Principal)"
        )
        release_lbl.setStyleSheet(
            f"font-size: 12px; color: {DARK_PALETTE.text_tertiary};"
        )

        # Línea explícita de versión requerida en "Acerca de".
        self.lbl_version_line = QLabel(f"Versión: {app_pkg.__version__}")
        self.lbl_version_line.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {DARK_PALETTE.accent_text};"
        )

        brand_col.addWidget(name_lbl)
        brand_col.addWidget(tagline)
        brand_col.addWidget(release_lbl)
        brand_col.addWidget(self.lbl_version_line)
        brand_row.addLayout(brand_col, stretch=1)
        card_layout.addLayout(brand_row)

        desc_lbl = QLabel(
            "Aplicación de escritorio nativa e independiente para gestionar y descargar contenido "
            "multimedia desde YouTube, TikTok, Instagram y Facebook mediante Arquitectura Hexagonal y Monolito Modular."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setObjectName("HintLabel")

        # Diagnóstico de FFmpeg
        self.lbl_ffmpeg_status = QLabel("Estado de FFmpeg: Verificando...")
        self.lbl_ffmpeg_status.setStyleSheet(
            f"font-size: 13px; color: {DARK_PALETTE.accent_text}; font-weight: 600;"
        )

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        btn_diagnostics = QPushButton("Exportar Paquete de Diagnóstico (.zip)")
        btn_diagnostics.setObjectName("SecondaryButton")

        btn_check_updates = QPushButton("Buscar actualizaciones")
        btn_check_updates.setObjectName("PrimaryButton")
        btn_check_updates.clicked.connect(self.update_check_requested.emit)
        buttons_row.addWidget(btn_diagnostics)
        buttons_row.addWidget(btn_check_updates)
        buttons_row.addStretch()

        card_layout.addWidget(desc_lbl)
        card_layout.addWidget(self.lbl_ffmpeg_status)
        card_layout.addSpacing(6)
        card_layout.addLayout(buttons_row)

        layout.addWidget(card)
        layout.addStretch()

    @staticmethod
    def _build_logo_pixmap(size: int = 64) -> QPixmap:
        """Logotipo vectorial: cuadrado redondeado verde con flecha de descarga."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(DARK_PALETTE.accent))
        radius = int(size * 0.24)
        painter.drawRoundedRect(0, 0, size, size, radius, radius)

        pen_color = QColor(DARK_PALETTE.text_on_accent)
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
            self.lbl_ffmpeg_status.setStyleSheet(
                f"font-size: 13px; color: {DARK_PALETTE.accent_text}; font-weight: 700;"
            )
        else:
            self.lbl_ffmpeg_status.setText("Estado de FFmpeg: No detectado (Modo streaming directo)")
            self.lbl_ffmpeg_status.setStyleSheet(
                f"font-size: 13px; color: {DARK_PALETTE.warning}; font-weight: 700;"
            )
