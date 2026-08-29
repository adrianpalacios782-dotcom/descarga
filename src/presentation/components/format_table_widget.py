"""Componentes para la tabla y selección estructurada de formatos de descarga.

Proporciona:
- FormatTableHeader: Cabecera con nombres de columna alineados.
- FormatTableRow: Fila de selección con radio button circular visible,
  columnas para Calidad, Formato, Tamaño, Códec, FPS y Estado/Recomendado.
- Panel de conversión de audio con selectores honestos de contenedor y bitrate.
"""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.format_option import AudioFormat, VideoQualityOption
from src.domain.services.content_preview import format_size_bytes

TAB_RECOMMENDED = "recommended"
TAB_VIDEO = "video"
TAB_AUDIO = "audio"


class FormatTableHeader(QFrame):
    """Fila de cabecera con los títulos de columna de la tabla de formatos."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("FormatTableHeader")
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Anchos alineados con las celdas de FormatTableRow
        col_select = QLabel("ELEGIR")
        col_select.setObjectName("TableHeaderCol")
        col_select.setFixedWidth(44)
        col_select.setAlignment(Qt.AlignmentFlag.AlignCenter)

        col_quality = QLabel("CALIDAD")
        col_quality.setObjectName("TableHeaderCol")
        col_quality.setFixedWidth(130)

        col_fmt = QLabel("FORMATO")
        col_fmt.setObjectName("TableHeaderCol")
        col_fmt.setFixedWidth(75)

        col_size = QLabel("TAMAÑO")
        col_size.setObjectName("TableHeaderCol")
        col_size.setFixedWidth(95)

        col_codec = QLabel("CÓDEC")
        col_codec.setObjectName("TableHeaderCol")
        col_codec.setFixedWidth(85)

        col_fps = QLabel("FPS")
        col_fps.setObjectName("TableHeaderCol")
        col_fps.setFixedWidth(65)

        col_status = QLabel("ESTADO")
        col_status.setObjectName("TableHeaderCol")

        layout.addWidget(col_select)
        layout.addWidget(col_quality)
        layout.addWidget(col_fmt)
        layout.addWidget(col_size)
        layout.addWidget(col_codec)
        layout.addWidget(col_fps)
        layout.addWidget(col_status, stretch=1)


class FormatTableRow(QFrame):
    """Fila de formato con columnas organizadas y selección visual inequívoca."""

    def __init__(
        self,
        vqo: Optional[VideoQualityOption] = None,
        af: Optional[AudioFormat] = None,
        is_recommended: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FormatRow")
        self.kind = "video" if vqo is not None else "audio"
        self.vqo = vqo
        self.af = af
        self.is_recommended = is_recommended
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(48)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 4, 14, 4)
        row.setSpacing(10)

        # 1. Columna Selección (Radio button circular visible y elegante)
        self.radio = QRadioButton()
        self.radio.setObjectName("QualityRadio")
        self.radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.radio.setFixedWidth(44)
        row.addWidget(self.radio, alignment=Qt.AlignmentFlag.AlignCenter)

        # 2. Columna Calidad
        quality_box = QHBoxLayout()
        quality_box.setSpacing(6)
        if self.kind == "video":
            assert vqo is not None
            q_text = vqo.label
            badge_text = vqo.badge
            format_text = vqo.extension.upper()
            size_human = format_size_bytes(vqo.estimated_size_bytes) if vqo.estimated_size_bytes else ""
            codec_text = (vqo.video_codec or "H.264").split(".")[0].upper()
            fps_text = f"{int(vqo.fps)} FPS" if vqo.fps and vqo.fps > 0 else "—"
            tech_info = vqo.get_technical_info()
        else:
            assert af is not None
            br = int(round(float(af.bitrate_kbps))) if af.bitrate_kbps else 0
            q_text = f"{br} kbps" if br else "Audio nativo"
            badge_text = "HQ" if br and br >= 192 else ""
            format_text = af.extension.upper()
            size_human = format_size_bytes(af.filesize_bytes) if af.filesize_bytes else ""
            codec_text = (af.audio_codec or af.extension).split(".")[0].upper()
            fps_text = "—"
            tech_info = f"Audio nativo · {af.extension.upper()}"

        self.lbl_quality = QLabel(q_text)
        self.lbl_quality.setObjectName("QualityTitle")
        quality_box.addWidget(self.lbl_quality)

        if badge_text:
            self.lbl_q_badge = QLabel(badge_text)
            self.lbl_q_badge.setObjectName("BadgeHD" if badge_text in ("HD", "2K", "4K") else "BadgeQuality")
            quality_box.addWidget(self.lbl_q_badge)
        quality_box.addStretch()

        quality_wrap = QWidget()
        quality_wrap.setStyleSheet("background: transparent;")
        quality_wrap.setLayout(quality_box)
        quality_wrap.setFixedWidth(130)
        row.addWidget(quality_wrap)

        # 3. Columna Formato
        self.lbl_format = QLabel(format_text)
        self.lbl_format.setObjectName("FormatColText")
        self.lbl_format.setFixedWidth(75)
        row.addWidget(self.lbl_format)

        # 4. Columna Tamaño
        size_display = f"~{size_human}" if size_human else "No disponible"
        self.size_label = QLabel(size_display)
        self.size_label.setObjectName("QualitySize")
        self.size_label.setFixedWidth(95)
        row.addWidget(self.size_label)

        # 5. Columna Códec
        self.lbl_codec = QLabel(codec_text)
        self.lbl_codec.setObjectName("TechColText")
        self.lbl_codec.setFixedWidth(85)
        row.addWidget(self.lbl_codec)

        # 6. Columna FPS
        self.lbl_fps = QLabel(fps_text)
        self.lbl_fps.setObjectName("TechColText")
        self.lbl_fps.setFixedWidth(65)
        row.addWidget(self.lbl_fps)

        # 7. Columna Estado / Recomendado
        status_box = QHBoxLayout()
        status_box.setSpacing(6)
        if self.is_recommended or (vqo and vqo.is_best_quality):
            self.lbl_rec_badge = QLabel("Recomendado")
            self.lbl_rec_badge.setObjectName("BadgeRecommended")
            status_box.addWidget(self.lbl_rec_badge)
        status_box.addStretch()

        # Botón de descarga rápida directa por fila (para compatibilidad o acción rápida)
        self.btn_download = QPushButton("Descargar")
        self.btn_download.setObjectName("FormatRowDownload")
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        status_box.addWidget(self.btn_download)

        status_wrap = QWidget()
        status_wrap.setStyleSheet("background: transparent;")
        status_wrap.setLayout(status_box)
        row.addWidget(status_wrap, stretch=1)

        # Atributos de compatibilidad con tests existentes
        # (title = QualityTitle, info = TechnicalInfo)
        if self.kind == "video" and vqo is not None:
            full_title = vqo.label if not vqo.badge else f"{vqo.label} · {vqo.badge}"
        else:
            full_title = q_text
        self.title = QLabel(full_title)
        self.title.hide()
        self.info = QLabel(tech_info)
        self.info.hide()

        self.radio.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.setProperty("selected", checked)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.radio.setChecked(True)
        super().mousePressEvent(event)


# Alias retrocompatible
FormatRow = FormatTableRow
