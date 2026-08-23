import os
import re
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFrame, QComboBox, QFileDialog, QRadioButton,
    QButtonGroup, QGridLayout, QApplication,
)

from src.domain.entities.format_option import DownloadType, VideoQualityOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import InvalidUrlError
from src.domain.services.content_preview import (
    extract_publication_year,
    format_size_bytes,
    truncate_text,
)
from src.domain.value_objects.url import Url
from src.presentation.components.animations import fade_in
from src.presentation.components.app_icons import download_icon
from src.presentation.components.thumbnail_loader import ThumbnailLabel
from src.presentation.styles.styles import DARK_PALETTE


SYNOPSIS_MAX_CHARS = 220
QUALITY_GRID_COLUMNS = 3
URL_VALIDATION_DELAY_MS = 350
CLIPBOARD_POLL_INTERVAL_MS = 1200

_CLIPBOARD_URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.)?(youtube\.com|youtu\.be|tiktok\.com|"
    r"instagram\.com|facebook\.com|fb\.watch)/\S+",
    re.IGNORECASE,
)

_PLATFORM_SPOTLIGHT = [
    ("YouTube", "#ff4d4d"),
    ("TikTok", "#69e2f0"),
    ("Instagram", "#f070a8"),
    ("Facebook", "#6ea8ff"),
]


class QualityOptionRow(QFrame):
    """Tarjeta seleccionable de una cuadrícula para una calidad de video real."""

    def __init__(self, vqo: VideoQualityOption, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("QualityCard")
        self.vqo = vqo
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        card = QVBoxLayout(self)
        card.setContentsMargins(14, 12, 14, 12)
        card.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.radio = QRadioButton(vqo.label)
        self.radio.setObjectName("QualityRadio")
        self.radio.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.radio)
        header.addStretch()
        if vqo.badge:
            badge_lbl = QLabel(vqo.badge)
            badge_lbl.setObjectName("QualityBadge")
            header.addWidget(badge_lbl)
        card.addLayout(header)

        info = QLabel(vqo.get_technical_info())
        info.setObjectName("QualityTechInfo")
        info.setWordWrap(True)
        self.info = info
        card.addWidget(info)

        size_human = format_size_bytes(vqo.estimated_size_bytes)
        if size_human:
            size_lbl = QLabel(f"~{size_human}")
            size_lbl.setObjectName("QualitySize")
            card.addWidget(size_lbl)

        self.radio.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.setProperty("selected", checked)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (convención Qt)
        self.radio.setChecked(True)
        super().mousePressEvent(event)


class InicioView(QWidget):
    """Vista principal: PEGAR -> ANALIZAR -> PREVISUALIZAR -> CALIDAD -> FORMATO -> DESCARGAR."""

    analyze_requested = Signal(str)
    download_requested = Signal(object, str, str)  # (media_metadata, format_id, destination_path)

    STATE_EMPTY = "empty"
    STATE_ANALYZING = "analyzing"
    STATE_SUCCESS = "success"
    STATE_ERROR = "error"

    TEXT_EMPTY = "Listo para descargar"
    TEXT_ANALYZING = "Analizando contenido..."
    TEXT_SUCCESS = "Contenido encontrado"
    TEXT_ERROR_TITLE = "No pudimos analizar este enlace"
    TEXT_ERROR_DETAIL = "El enlace no es compatible o la plataforma no respondió."
    TEXT_NO_DESCRIPTION = "Sin descripción disponible."
    TEXT_NOT_AVAILABLE = "No disponible"
    TEXT_NO_VIDEO_QUALITIES = "Este contenido no ofrece calidades de video compatibles."
    TEXT_NO_AUDIO = "Este contenido no ofrece pistas de audio compatibles."

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_metadata: Optional[MediaMetadata] = None
        self.selected_type: DownloadType = DownloadType.VIDEO
        self._synopsis_full: str = ""
        self._quality_rows: List[QualityOptionRow] = []
        self._animations_enabled: bool = True
        self._clipboard_last_seen: str = ""
        # Creado antes de conectar señales de combos: _update_size_estimate lo usa.
        self.lbl_selection_summary = QLabel("")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 28)
        root.setSpacing(14)

        # ---------------------------------------------------- Encabezado
        # Oculto en estado vacío: el héroe lo sustituye como portada.
        self.header_title = QLabel("Descarga contenido multimedia")
        self.header_title.setObjectName("ViewTitle")
        self.header_subtitle = QLabel("Analiza el enlace y elige calidad antes de descargar.")
        self.header_subtitle.setObjectName("ViewSubtitle")
        self.header_title.hide()
        self.header_subtitle.hide()
        root.addWidget(self.header_title)
        root.addWidget(self.header_subtitle)

        # --------------------------------------------- Estado vacío héroe
        self.hero_widget = self._build_hero_widget()
        self.hero_wrap = QWidget()
        hero_wrap_layout = QVBoxLayout(self.hero_wrap)
        hero_wrap_layout.setContentsMargins(0, 0, 0, 0)
        hero_wrap_layout.addWidget(self.hero_widget)
        root.addWidget(self.hero_wrap, stretch=1)

        # ------------------------------------- Sugerencia del portapapeles
        self.clipboard_banner = QFrame()
        self.clipboard_banner.setObjectName("ClipboardBanner")
        banner_layout = QHBoxLayout(self.clipboard_banner)
        banner_layout.setContentsMargins(12, 8, 10, 8)
        banner_layout.setSpacing(10)
        self.lbl_clipboard_url = QLabel("")
        self.lbl_clipboard_url.setObjectName("ClipboardText")
        btn_clip_analyze = QPushButton("Analizar")
        btn_clip_analyze.setObjectName("SecondaryButton")
        btn_clip_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clip_analyze.clicked.connect(self._on_clipboard_analyze)
        banner_layout.addWidget(self.lbl_clipboard_url, stretch=1)
        banner_layout.addWidget(btn_clip_analyze)
        self.clipboard_banner.hide()
        root.addWidget(self.clipboard_banner)

        # --------------------------------------- Campo de URL con acciones
        url_box = QHBoxLayout()
        url_box.setSpacing(12)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText(
            "Pega aquí el enlace de YouTube, TikTok, Instagram o Facebook"
        )
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self._on_analyze_clicked)
        self.url_input.textChanged.connect(self._on_url_edited)

        self.btn_paste = QPushButton("Pegar")
        self.btn_paste.setObjectName("SecondaryButton")
        self.btn_paste.setMinimumHeight(40)
        self.btn_paste.setToolTip("Pegar desde el portapapeles")
        self.btn_paste.clicked.connect(self._on_paste_clicked)

        self.btn_analyze = QPushButton("Analizar")
        self.btn_analyze.setObjectName("PrimaryButton")
        self.btn_analyze.setMinimumWidth(130)
        self.btn_analyze.setMinimumHeight(40)
        self.btn_analyze.clicked.connect(self._on_analyze_clicked)

        url_box.addWidget(self.url_input, stretch=1)
        url_box.addWidget(self.btn_paste)
        url_box.addWidget(self.btn_analyze)
        root.addLayout(url_box)

        # Banner de estado (vacío / analizando / éxito / error)
        self.lbl_status = QLabel(self.TEXT_EMPTY)
        self.lbl_status.setObjectName("StatusLabel")
        self.lbl_status.setProperty("state", self.STATE_EMPTY)
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        # --------------------------------------- Card de previsualización
        self.preview_card = QFrame()
        self.preview_card.setObjectName("Card")
        self.preview_card.hide()

        card = QVBoxLayout(self.preview_card)
        card.setContentsMargins(22, 20, 22, 20)
        card.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        self.thumbnail = ThumbnailLabel(320, 180)
        top_row.addWidget(self.thumbnail, alignment=Qt.AlignmentFlag.AlignTop)

        info_col = QVBoxLayout()
        info_col.setSpacing(8)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        self.chip_platform = self._make_chip(accent=True)
        self.chip_duration = self._make_chip()
        self.chip_year = self._make_chip()
        self.chip_quality = self._make_chip()
        for chip in (self.chip_platform, self.chip_duration, self.chip_year, self.chip_quality):
            chips_row.addWidget(chip)
            chip.hide()
        chips_row.addStretch()
        info_col.addLayout(chips_row)

        self.lbl_title = QLabel("")
        self.lbl_title.setObjectName("PreviewTitle")
        self.lbl_title.setWordWrap(True)
        info_col.addWidget(self.lbl_title)

        self.lbl_channel = QLabel("")
        self.lbl_channel.setObjectName("PreviewChannel")
        info_col.addWidget(self.lbl_channel)
        info_col.addStretch()

        top_row.addLayout(info_col, stretch=1)
        card.addLayout(top_row)

        # Sección Sinopsis
        synopsis_box = QVBoxLayout()
        synopsis_box.setSpacing(4)
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
        card.addLayout(synopsis_box)

        # Sección Calidad (cuadrícula de tarjetas con calidades reales)
        lbl_quality = QLabel("CALIDAD DE VIDEO")
        lbl_quality.setObjectName("SectionHeader")
        card.addSpacing(4)
        card.addWidget(lbl_quality)

        self.quality_container = QWidget()
        self.quality_layout = QGridLayout(self.quality_container)
        self.quality_layout.setContentsMargins(0, 0, 0, 0)
        self.quality_layout.setSpacing(10)
        card.addWidget(self.quality_container)

        self.quality_button_group = QButtonGroup(self)
        self.quality_button_group.setExclusive(True)

        # Selector segmentado de modo: VÍDEO | AUDIO
        lbl_format = QLabel("FORMATO")
        lbl_format.setObjectName("SectionHeader")
        card.addWidget(lbl_format)

        segment_container = QWidget()
        segment_container.setObjectName("SegmentContainer")
        segment_container.setFixedHeight(44)
        seg_layout = QHBoxLayout(segment_container)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(2)
        self.btn_format_video = QPushButton("Vídeo")
        self.btn_format_video.setObjectName("SegmentButton")
        self.btn_format_video.setCheckable(True)
        self.btn_format_video.setChecked(True)
        self.btn_format_audio = QPushButton("Audio")
        self.btn_format_audio.setObjectName("SegmentButton")
        self.btn_format_audio.setCheckable(True)
        self.format_button_group = QButtonGroup(self)
        self.format_button_group.setExclusive(True)
        self.format_button_group.addButton(self.btn_format_video)
        self.format_button_group.addButton(self.btn_format_audio)
        seg_layout.addWidget(self.btn_format_video)
        seg_layout.addWidget(self.btn_format_audio)
        seg_layout.addStretch()
        format_row = QHBoxLayout()
        format_row.addWidget(segment_container)
        format_row.addStretch()
        card.addLayout(format_row)

        self.btn_format_video.toggled.connect(lambda checked: self._set_download_mode(DownloadType.VIDEO) if checked else None)
        self.btn_format_audio.toggled.connect(lambda checked: self._set_download_mode(DownloadType.AUDIO) if checked else None)

        # Panel AUDIO (formato contenedor + bitrate honestos)
        self.panel_audio = QWidget()
        self.panel_audio.hide()
        a_layout = QHBoxLayout(self.panel_audio)
        a_layout.setContentsMargins(0, 0, 0, 0)
        a_layout.setSpacing(12)
        lbl_a_fmt = QLabel("Contenedor:")
        lbl_a_fmt.setObjectName("FieldLabel")
        self.combo_audio_fmt = QComboBox()
        self.combo_audio_fmt.addItem("MP3", userData="mp3")
        self.combo_audio_fmt.addItem("M4A", userData="m4a")
        self.combo_audio_fmt.addItem("WAV", userData="wav")
        lbl_a_br = QLabel("Bitrate:")
        lbl_a_br.setObjectName("FieldLabel")
        self.combo_audio_br = QComboBox()
        self.lbl_audio_note = QLabel("La conversión mantiene la calidad original del audio; no la aumenta.")
        self.lbl_audio_note.setObjectName("HintLabel")
        self.lbl_audio_note.setWordWrap(True)
        a_layout.addWidget(lbl_a_fmt)
        a_layout.addWidget(self.combo_audio_fmt, stretch=1)
        a_layout.addWidget(lbl_a_br)
        a_layout.addWidget(self.combo_audio_br, stretch=1)
        card.addWidget(self.panel_audio)
        card.addWidget(self.lbl_audio_note)
        self.lbl_audio_note.hide()

        # Tamaño estimado de la selección actual
        self.lbl_size_estimate = QLabel("")
        self.lbl_size_estimate.setObjectName("SizeEstimate")
        card.addWidget(self.lbl_size_estimate)

        self.combo_audio_fmt.currentIndexChanged.connect(self._refresh_audio_bitrate_options)
        self.combo_audio_fmt.currentIndexChanged.connect(lambda _: self._update_size_estimate())
        self.combo_audio_br.currentIndexChanged.connect(lambda _: self._update_size_estimate())
        self._refresh_audio_bitrate_options()

        # Carpeta de destino
        dest_layout = QHBoxLayout()
        dest_layout.setSpacing(12)
        lbl_dest = QLabel("Guardar en:")
        lbl_dest.setObjectName("FieldLabel")
        self.txt_dest = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads"))
        btn_browse = QPushButton("Examinar...")
        btn_browse.setObjectName("SecondaryButton")
        btn_browse.clicked.connect(self._on_browse_dest)
        dest_layout.addWidget(lbl_dest)
        dest_layout.addWidget(self.txt_dest, stretch=1)
        dest_layout.addWidget(btn_browse)
        card.addLayout(dest_layout)

        # Acción principal protagonista + resumen de la selección
        action_col = QVBoxLayout()
        action_col.setSpacing(6)
        self.btn_download = QPushButton("Descargar")
        self.btn_download.setObjectName("DownloadButton")
        self.btn_download.setIcon(download_icon(DARK_PALETTE.text_on_accent))
        self.btn_download.setIconSize(QSize(18, 18))
        self.btn_download.setMinimumHeight(50)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self._on_download_clicked)
        self.lbl_selection_summary.setObjectName("DownloadSummary")
        self.lbl_selection_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_col.addWidget(self.btn_download)
        action_col.addWidget(self.lbl_selection_summary)
        card.addLayout(action_col)

        root.addWidget(self.preview_card)
        root.addStretch(0)

        # ------------------------------------------- Timers de ayuda UX
        # Validación en vivo del enlace (con debounce para no validar a medias).
        self._url_validate_timer = QTimer(self)
        self._url_validate_timer.setSingleShot(True)
        self._url_validate_timer.setInterval(URL_VALIDATION_DELAY_MS)
        self._url_validate_timer.timeout.connect(self._validate_url_now)

        # Vigilancia discreta del portapapeles: solo sugiere, nunca analiza sola.
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.setInterval(CLIPBOARD_POLL_INTERVAL_MS)
        self._clipboard_timer.timeout.connect(self._poll_clipboard)
        self._clipboard_timer.start()

    # ------------------------------------------------------------- Héroe
    @staticmethod
    def _build_hero_widget() -> QFrame:
        hero = QFrame()
        hero.setObjectName("HeroCard")
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(24, 48, 24, 48)
        layout.setSpacing(12)

        headline = QLabel("¿Qué quieres descargar?")
        headline.setObjectName("HeroTitle")
        headline.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        hint = QLabel("Pega un enlace arriba y te mostraremos el contenido antes de descargarlo.")
        hint.setObjectName("HeroSubtitle")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        platforms_row = QHBoxLayout()
        platforms_row.setSpacing(18)
        platforms_row.addStretch()
        for name, color in _PLATFORM_SPOTLIGHT:
            dot = QLabel(
                f'<span style="color:{color}; font-size:11px;">●</span>'
                f'&nbsp;<span style="font-size:12px;">{name}</span>'
            )
            platforms_row.addWidget(dot)
        platforms_row.addStretch()

        layout.addStretch()
        layout.addWidget(headline)
        layout.addWidget(hint)
        layout.addSpacing(10)
        layout.addLayout(platforms_row)
        layout.addStretch()
        return hero

    # ------------------------------------------------------------- Estado UI
    @staticmethod
    def _make_chip(accent: bool = False) -> QLabel:
        chip = QLabel("")
        chip.setObjectName("ChipAccent" if accent else "Chip")
        chip.setVisible(False)
        return chip

    def _set_state_banner(self, state: str, text: str) -> None:
        self.lbl_status.setText(text)
        self.lbl_status.setProperty("state", state)
        style = self.lbl_status.style()
        if style is not None:
            style.unpolish(self.lbl_status)
            style.polish(self.lbl_status)

    def set_animations_enabled(self, enabled: bool) -> None:
        self._animations_enabled = bool(enabled)

    def set_analyzing_state(self, is_analyzing: bool) -> None:
        if is_analyzing:
            self.btn_analyze.setEnabled(False)
            self.btn_analyze.setText("Analizando...")
            self.url_input.setEnabled(False)
            self.clipboard_banner.hide()
            self._set_state_banner(self.STATE_ANALYZING, self.TEXT_ANALYZING)
            self._show_header(show=True)
            self.hero_wrap.hide()
            self.preview_card.hide()
        else:
            self.btn_analyze.setEnabled(True)
            self.btn_analyze.setText("Analizar")
            self.url_input.setEnabled(True)
            if self.current_metadata is not None:
                self._set_state_banner(self.STATE_SUCCESS, self.TEXT_SUCCESS)
                self._show_header(show=True)
            else:
                self._set_state_banner(self.STATE_EMPTY, self.TEXT_EMPTY)
                self._show_header(show=False)
                self.hero_wrap.show()

    def _show_header(self, show: bool) -> None:
        """La cabecera compacta aparece cuando el héroe se retira."""
        self.header_title.setVisible(show)
        self.header_subtitle.setVisible(show)

    def show_error(self, message: str) -> None:
        self.current_metadata = None
        self.preview_card.hide()
        self.hero_wrap.hide()
        self._show_header(show=True)
        detail = self._sanitize_error_message(message)
        text = f"{self.TEXT_ERROR_TITLE}. {self.TEXT_ERROR_DETAIL}"
        if detail:
            text = f"{text}\n{detail}"
        self._set_state_banner(self.STATE_ERROR, text)

    @staticmethod
    def _sanitize_error_message(message: str) -> str:
        """Reduce el mensaje técnico a una línea corta sin trazas internas."""
        if not message:
            return ""
        cleaned = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", str(message))
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(("Traceback", 'File "')) or '"line ' in line or line.startswith("^"):
                continue
            for marker in ("Traceback", 'File "'):
                idx = line.find(marker)
                if idx > 0:
                    line = line[:idx].strip()
            if line:
                return line[:200]
        return ""

    def _on_analyze_clicked(self) -> None:
        url_str = self.url_input.text().strip()
        if url_str:
            self.clipboard_banner.hide()
            self.analyze_requested.emit(url_str)

    # -------------------------------------------------- URL: pegar y validar
    def _on_paste_clicked(self) -> None:
        clipboard_text = QApplication.clipboard().text().strip()
        if clipboard_text:
            self.url_input.setText(clipboard_text)
            self.url_input.setFocus()
            self.url_input.end(False)

    def _on_url_edited(self, text: str) -> None:
        self.clipboard_banner.hide()
        self._url_validate_timer.start()

    def _validate_url_now(self) -> None:
        """Marca el campo como válido/inválido usando el mismo criterio del dominio."""
        text = self.url_input.text().strip()
        state = ""
        tooltip = ""
        if text:
            try:
                Url(text)
                state = "valid"
            except InvalidUrlError as ex:
                state = "invalid"
                tooltip = str(ex)
        self._apply_url_state(state, tooltip)

    def _apply_url_state(self, state: str, tooltip: str = "") -> None:
        for prop in ("valid", "invalid"):
            self.url_input.setProperty(prop, False)
        if state in ("valid", "invalid"):
            self.url_input.setProperty(state, True)
        self.url_input.setToolTip(tooltip)
        style = self.url_input.style()
        if style is not None:
            style.unpolish(self.url_input)
            style.polish(self.url_input)

    # ------------------------------------------------------------ Portapapeles
    def _poll_clipboard(self) -> None:
        """Muestra una sugerencia discreta si el portapapeles trae un enlace compatible."""
        if not self.isVisible() or not self.btn_analyze.isEnabled():
            return
        text = QApplication.clipboard().text().strip()
        if (
            not text
            or text == self._clipboard_last_seen
            or text == self.url_input.text().strip()
            or not _CLIPBOARD_URL_PATTERN.match(text)
        ):
            return
        self._clipboard_last_seen = text
        display = text if len(text) <= 64 else text[:61] + "..."
        self.lbl_clipboard_url.setText(f"Enlace detectado · {display}")
        self.clipboard_banner.show()

    def _on_clipboard_analyze(self) -> None:
        candidate = self._clipboard_last_seen
        if candidate:
            self.url_input.setText(candidate)
            self._on_analyze_clicked()

    # ------------------------------------------------------- Previsualización
    def set_metadata(self, metadata: MediaMetadata) -> None:
        self.current_metadata = metadata
        self._synopsis_full = metadata.description or ""
        self.set_analyzing_state(False)

        self.lbl_title.setText(metadata.title or self.TEXT_NOT_AVAILABLE)
        channel = (metadata.author or "").strip()
        self.lbl_channel.setText(f"Canal: {channel}" if channel else f"Canal: {self.TEXT_NOT_AVAILABLE}")

        self._populate_chips(metadata)
        self.thumbnail.load_from_url(metadata.thumbnail_url or "")
        self._render_synopsis(show_truncated=True)
        self._rebuild_quality_options(metadata)

        if not self.quality_button_group.buttons() and metadata.audio_formats:
            self.btn_format_audio.setChecked(True)
        elif metadata.video_quality_options or metadata.video_formats:
            self.btn_format_video.setChecked(True)

        self._update_size_estimate()
        self._update_download_availability()
        self.hero_wrap.hide()
        self._show_header(show=True)
        self.preview_card.show()
        fade_in(self.preview_card, enabled=self._animations_enabled)

    def _populate_chips(self, metadata: MediaMetadata) -> None:
        self.chip_platform.setText(metadata.platform or self.TEXT_NOT_AVAILABLE)
        self.chip_platform.show() if metadata.platform else self.chip_platform.hide()

        duration = metadata.get_duration_formatted() if metadata.duration_seconds > 0 else ""
        if duration:
            self.chip_duration.setText(f"Duración {duration}")
            self.chip_duration.show()
        else:
            self.chip_duration.hide()

        year = extract_publication_year(metadata.upload_date)
        if year:
            self.chip_year.setText(f"Publicado en {year}")
            self.chip_year.show()
        else:
            self.chip_year.hide()

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
        if not self._synopsis_full.strip():
            self.lbl_synopsis.setText(self.TEXT_NO_DESCRIPTION)
            self.btn_toggle_synopsis.hide()
            return
        truncated = truncate_text(self._synopsis_full, SYNOPSIS_MAX_CHARS)
        needs_truncation = len(truncated) < len(self._synopsis_full.strip())
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

    # --------------------------------------------------------- Opciones UI
    def _rebuild_quality_options(self, metadata: MediaMetadata) -> None:
        while self.quality_layout.count():
            item = self.quality_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for radio in self.quality_button_group.buttons():
            self.quality_button_group.removeButton(radio)

        self._quality_rows.clear()

        options = metadata.video_quality_options
        if not options and metadata.video_formats:
            options = self._fallback_quality_options(metadata)

        for index, vqo in enumerate(options):
            row = QualityOptionRow(vqo)
            self._quality_rows.append(row)
            self.quality_button_group.addButton(row.radio)
            grid_row, grid_col = divmod(index, QUALITY_GRID_COLUMNS)
            self.quality_layout.addWidget(row, grid_row, grid_col)
            row.radio.toggled.connect(lambda checked, r=row: self._on_quality_selected(r) if checked else None)

        if options:
            self.quality_container.show()
            self._quality_rows[0].radio.setChecked(True)
        else:
            self.quality_container.hide()

        self._update_download_availability()

    def _update_download_availability(self) -> None:
        """Habilita/deshabilita el botón Descargar según la selección posible.

        Reemplaza el antiguo QMessageBox 'Selección Requerida': los errores de
        validación normales se comunican inline, nunca con diálogos modales.
        Es el ÚNICO escritor del resumen cuando la descarga no es posible.
        """
        if self.current_metadata is None:
            self.btn_download.setEnabled(False)
            return

        can_download = False
        message = ""
        if self.selected_type == DownloadType.VIDEO:
            has_qualities = bool(self._iter_quality_rows())
            can_download = has_qualities
            if not has_qualities:
                message = self.TEXT_NO_VIDEO_QUALITIES
        else:
            has_audio = bool(self.current_metadata.audio_formats)
            can_download = has_audio
            if not has_audio:
                message = self.TEXT_NO_AUDIO

        self.btn_download.setEnabled(can_download)
        if can_download:
            self._update_size_estimate()
        else:
            self.lbl_selection_summary.setText(message)

    @staticmethod
    def _fallback_quality_options(metadata: MediaMetadata):
        from src.domain.entities.format_option import VideoQualityOption

        options = []
        for vf in metadata.video_formats:
            if not vf.height or vf.is_best_quality:
                continue
            badge = "HD" if vf.height in (1080, 720) else ("4K" if vf.height >= 2160 else "")
            options.append(VideoQualityOption(
                height=vf.height,
                label=f"{vf.height}p",
                badge=badge,
                video_format_id=vf.format_id,
                audio_format_id=vf.audio_format_id,
                needs_ffmpeg_merge=vf.needs_ffmpeg_merge,
                estimated_size_bytes=vf.filesize_bytes,
                fps=vf.fps,
                extension=vf.extension,
                width=vf.width,
                video_codec=vf.video_codec
            ))
        return options

    def _selected_quality_option(self) -> Optional[VideoQualityOption]:
        for row in self._iter_quality_rows():
            if row.radio.isChecked():
                return row.vqo
        return None

    def _iter_quality_rows(self):
        return list(self._quality_rows)

    def _on_quality_selected(self, row: QualityOptionRow) -> None:
        self._update_size_estimate()

    def _set_download_mode(self, mode: DownloadType) -> None:
        self.selected_type = mode
        if mode == DownloadType.VIDEO:
            self.btn_format_video.setChecked(True)
            self.panel_audio.hide()
            self.lbl_audio_note.hide()
        else:
            self.btn_format_audio.setChecked(True)
            self.panel_audio.show()
            self.lbl_audio_note.show()
        self._update_download_availability()

    def _refresh_audio_bitrate_options(self) -> None:
        """Actualiza los bitrates ofrecidos según el formato de audio (honestos y producibles)."""
        current = self.combo_audio_fmt.currentData()
        self.combo_audio_br.clear()

        if current == "mp3":
            for br in (320, 256, 192, 128):
                self.combo_audio_br.addItem(f"{br} kbps", userData=br)
            self.combo_audio_br.setEnabled(True)
        elif current == "m4a":
            for br in (192, 160, 128):
                self.combo_audio_br.addItem(f"{br} kbps", userData=br)
            self.combo_audio_br.setEnabled(True)
        else:  # wav: sin compresión, el bitrate no aplica
            self.combo_audio_br.addItem("Sin compresión", userData=320)
            self.combo_audio_br.setEnabled(False)

    def _update_size_estimate(self) -> None:
        summary_parts: List[str] = []

        if self.current_metadata is None:
            self.lbl_size_estimate.setText("")
            self.lbl_selection_summary.setText("")
            return

        size_bytes = None
        context = ""
        if self.selected_type == DownloadType.VIDEO:
            vqo = self._selected_quality_option()
            if vqo is not None:
                size_bytes = vqo.estimated_size_bytes
                context = f"{vqo.extension.upper()} · {vqo.label}"
                summary_parts.extend([vqo.label, vqo.extension.upper()])
        else:
            audio_formats = self.current_metadata.audio_formats
            if audio_formats:
                af = audio_formats[0]
                size_bytes = af.filesize_bytes
                target_fmt = str(self.combo_audio_fmt.currentData() or "").upper()
                bitrate = self.combo_audio_br.currentData()
                context = f"{target_fmt}" + (f" · {bitrate} kbps" if bitrate else "")
                summary_parts.append(target_fmt)
                if bitrate:
                    summary_parts.append(f"{bitrate} kbps")

        human = format_size_bytes(size_bytes)
        if human:
            self.lbl_size_estimate.setText(f"Tamaño estimado: ~{human}" + (f" · {context}" if context else ""))
            summary_parts.insert(0, human.replace(" ", ""))
        else:
            self.lbl_size_estimate.setText("Tamaño estimado no disponible" + (f" · {context}" if context else ""))

        if summary_parts:
            self.lbl_selection_summary.setText(" · ".join(summary_parts))
        else:
            self.lbl_selection_summary.setText("")

    # ------------------------------------------------------------ Descarga
    def _on_browse_dest(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino")
        if directory:
            self.txt_dest.setText(directory)

    def _on_download_clicked(self) -> None:
        if not self.current_metadata:
            return

        # Validación inline (sin QMessageBox): si no hay selección posible el botón
        # permanece deshabilitado y el resumen explica el motivo.
        if not self.btn_download.isEnabled():
            return

        dest_dir = self.txt_dest.text().strip()
        if not os.path.isdir(dest_dir):
            self._show_warning("Ruta Inválida", "La carpeta de destino no existe o no es válida.")
            return

        title = self._sanitize_filename(self.current_metadata.title)

        if self.selected_type == DownloadType.VIDEO:
            vqo = self._selected_quality_option()
            if vqo is None:
                # Defensa adicional: sin calidad seleccionada no se emite la descarga.
                self.lbl_selection_summary.setText(self.TEXT_NO_VIDEO_QUALITIES)
                return
            if vqo.is_best_quality:
                fmt_id = "vq_best"
                filename = f"{title} - Mejor calidad.mp4"
            else:
                fmt_id = f"vq_{vqo.height}"
                filename = f"{title} - {vqo.height}p.mp4"
        else:
            target_fmt = str(self.combo_audio_fmt.currentData())
            target_br = int(self.combo_audio_br.currentData())
            best_af = self.current_metadata.audio_formats[0] if self.current_metadata.audio_formats else None
            af_id = best_af.format_id if best_af else "best_audio"
            fmt_id = f"audio_{af_id}_{target_fmt}_{target_br}"
            filename = f"{title}.{target_fmt}"

        dest_path = os.path.join(dest_dir, filename)
        self.download_requested.emit(self.current_metadata, fmt_id, dest_path)

    def _show_warning(self, title: str, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, title, message)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitiza un nombre de archivo eliminando caracteres peligrosos."""
        if not name:
            return "descarga"
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        cleaned = cleaned.strip().rstrip(".")
        if not cleaned:
            return "descarga"
        return cleaned[:180]
