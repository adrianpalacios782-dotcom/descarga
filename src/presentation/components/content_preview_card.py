"""Componente de previsualización del contenido multimedia analizado.

Presenta de forma compacta y visualmente jerarquizada:
- Miniatura proporcional (16:9) con esquinas redondeadas y badge de duración.
- Fila de chips técnicos: plataforma, tipo de contenido, duración, año, calidad máxima.
- Título destacado y canal/autor.
- Sinopsis corta colapsable con control [Ver más] / [Ver menos].
"""

import re
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.media_metadata import MediaMetadata
from src.domain.services.content_preview import (
    extract_publication_year,
    truncate_text,
)
from src.presentation.components.thumbnail_loader import ThumbnailLabel

SYNOPSIS_MAX_CHARS = 180


class ThumbWithBadge(QFrame):
    """Miniatura con borde redondeado y badge de duración superpuesto."""

    def __init__(self, thumbnail: ThumbnailLabel, badge: QLabel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ThumbWrap")
        self.setFixedSize(thumbnail.width(), thumbnail.height())
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(thumbnail, 0, 0)
        grid.addWidget(badge, 0, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)


class ContentPreviewCard(QFrame):
    """Tarjeta de previsualización de información del contenido analizado."""

    TEXT_NO_DESCRIPTION = "Sin descripción disponible."
    TEXT_NOT_AVAILABLE = "No disponible"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._synopsis_full: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # -------------------------------- Fila superior: Miniatura + Metadatos
        top_row = QHBoxLayout()
        top_row.setSpacing(18)

        self.thumbnail = ThumbnailLabel(280, 158, corner_radius=12)
        self.lbl_duration_badge = QLabel("")
        self.lbl_duration_badge.setObjectName("DurationBadge")
        self.lbl_duration_badge.hide()
        self.thumb_wrap = ThumbWithBadge(self.thumbnail, self.lbl_duration_badge)
        top_row.addWidget(self.thumb_wrap, alignment=Qt.AlignmentFlag.AlignTop)

        info_col = QVBoxLayout()
        info_col.setSpacing(6)

        # Chips de plataforma y detalles técnicos
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)

        self.chip_platform = self._make_chip(accent=True)
        self.chip_content_type = self._make_chip()
        self.chip_duration = self._make_chip()
        self.chip_year = self._make_chip()
        self.chip_quality = self._make_chip()

        for chip in (
            self.chip_platform,
            self.chip_content_type,
            self.chip_duration,
            self.chip_year,
            self.chip_quality,
        ):
            chips_row.addWidget(chip)
            chip.hide()

        chips_row.addStretch()
        info_col.addLayout(chips_row)

        # Título principal
        self.lbl_title = QLabel("")
        self.lbl_title.setObjectName("PreviewTitle")
        self.lbl_title.setWordWrap(True)
        info_col.addWidget(self.lbl_title)

        # Canal / Autor
        self.lbl_channel = QLabel("")
        self.lbl_channel.setObjectName("PreviewChannel")
        info_col.addWidget(self.lbl_channel)

        info_col.addStretch()
        top_row.addLayout(info_col, stretch=1)
        layout.addLayout(top_row)

        # -------------------------------- Sinopsis / Descripción colapsable
        synopsis_box = QVBoxLayout()
        synopsis_box.setSpacing(3)

        lbl_syn_header = QLabel("SINOPSIS")
        lbl_syn_header.setObjectName("SectionHeader")

        self.lbl_synopsis = QLabel("")
        self.lbl_synopsis.setObjectName("SynopsisText")
        self.lbl_synopsis.setWordWrap(True)

        self.btn_toggle_synopsis = QPushButton("Ver más")
        self.btn_toggle_synopsis.setObjectName("LinkButton")
        self.btn_toggle_synopsis.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_synopsis.hide()
        self.btn_toggle_synopsis.clicked.connect(self._toggle_synopsis)

        synopsis_box.addWidget(lbl_syn_header)
        synopsis_box.addWidget(self.lbl_synopsis)
        synopsis_box.addWidget(self.btn_toggle_synopsis, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(synopsis_box)

    @staticmethod
    def _make_chip(accent: bool = False) -> QLabel:
        chip = QLabel("")
        chip.setObjectName("ChipAccent" if accent else "Chip")
        chip.setVisible(False)
        return chip

    def set_metadata(self, metadata: MediaMetadata) -> None:
        """Carga y visualiza los datos reales del contenido sin inventar nada."""
        self._synopsis_full = (metadata.description or "").strip()

        self.lbl_title.setText(metadata.title or self.TEXT_NOT_AVAILABLE)
        channel = (metadata.author or "").strip()
        self.lbl_channel.setText(f"Canal: {channel}" if channel else f"Canal: {self.TEXT_NOT_AVAILABLE}")

        self._populate_chips(metadata)
        self.thumbnail.load_from_url(metadata.thumbnail_url or "")
        self._render_synopsis(show_truncated=True)

    def _populate_chips(self, metadata: MediaMetadata) -> None:
        # Plataforma
        if metadata.platform:
            self.chip_platform.setText(metadata.platform)
            self.chip_platform.show()
        else:
            self.chip_platform.hide()

        # Tipo de contenido
        is_audio_only = not metadata.video_quality_options and bool(metadata.audio_formats)
        content_type_label = "Audio" if is_audio_only else "Vídeo"
        self.chip_content_type.setText(content_type_label)
        self.chip_content_type.show()

        # Duración
        duration = metadata.get_duration_formatted() if metadata.duration_seconds > 0 else ""
        if duration:
            self.chip_duration.setText(f"Duración {duration}")
            self.chip_duration.show()
        else:
            self.chip_duration.hide()

        self.lbl_duration_badge.setText(duration)
        self.lbl_duration_badge.setVisible(bool(duration))

        # Año de publicación
        year = extract_publication_year(metadata.upload_date)
        if year:
            self.chip_year.setText(f"Publicado en {year}")
            self.chip_year.show()
        else:
            self.chip_year.hide()

        # Calidad máxima real
        heights = [v.height for v in metadata.video_quality_options if v.height and not v.is_best_quality]
        if heights:
            max_h = max(heights)
            badge_4k = any(v.badge == "4K" for v in metadata.video_quality_options)
            label = "Hasta 4K" if badge_4k and max_h >= 2160 else f"Hasta {max_h}p"
            self.chip_quality.setText(label)
            self.chip_quality.show()
        else:
            self.chip_quality.hide()

    def _render_synopsis(self, show_truncated: bool) -> None:
        if not self._synopsis_full:
            self.lbl_synopsis.setText(self.TEXT_NO_DESCRIPTION)
            self.btn_toggle_synopsis.hide()
            return

        truncated = truncate_text(self._synopsis_full, SYNOPSIS_MAX_CHARS)
        needs_truncation = len(truncated) < len(self._synopsis_full)

        if show_truncated and needs_truncation:
            self.lbl_synopsis.setText(truncated)
            self.btn_toggle_synopsis.setText("Ver más")
            self.btn_toggle_synopsis.show()
        else:
            self.lbl_synopsis.setText(self._synopsis_full)
            if needs_truncation:
                self.btn_toggle_synopsis.setText("Ver menos")
                self.btn_toggle_synopsis.show()
            else:
                self.btn_toggle_synopsis.hide()

    def _toggle_synopsis(self) -> None:
        showing_more = self.btn_toggle_synopsis.text() == "Ver menos"
        self._render_synopsis(show_truncated=showing_more)
