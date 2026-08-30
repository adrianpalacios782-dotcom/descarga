"""Vista principal de análisis y descarga (Studio / InicioView).

Flujo de interacción:
PEGAR URL → ANALIZAR → PREVISUALIZAR CONTENIDO → ELEGIR FORMATO → CONFIGURAR → INICIAR DESCARGA.

Estructura modular:
- ContentPreviewCard: miniatura proporcional, chips de metadatos y sinopsis colapsable.
- FormatTableHeader y FormatTableRow: tabla estructurada con columnas legibles y selector circular.
- DownloadConfigWidget: carpeta de destino y nombre de archivo editable.
- Barra de acción: tamaño estimado ("El tamaño es aproximado") y botón destacado de descarga.
"""

import os
import re
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.format_option import DownloadType, VideoQualityOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import InvalidUrlError
from src.domain.services.content_preview import (
    format_size_bytes,
)
from src.domain.services.filename_sanitizer import sanitize_filename
from src.domain.services.url_sanitizer import sanitize_single_video_url
from src.domain.value_objects.url import Url
from src.presentation.components.animations import fade_in
from src.presentation.components.app_icons import download_icon, search_icon
from src.presentation.components.content_preview_card import ContentPreviewCard
from src.presentation.components.download_config_widget import DownloadConfigWidget
from src.presentation.components.format_table_widget import (
    TAB_AUDIO,
    TAB_RECOMMENDED,
    TAB_VIDEO,
    FormatTableHeader,
    FormatTableRow,
)
from src.presentation.styles.styles import DARK_PALETTE

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


class InicioView(QWidget):
    """Vista de análisis y descarga con tabla de selección técnica y configuración."""

    analyze_requested = Signal(str)
    download_requested = Signal(object, str, str)  # (media_metadata, format_id, destination_path)
    batch_requested = Signal()

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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_metadata: Optional[MediaMetadata] = None
        self.selected_type: DownloadType = DownloadType.VIDEO
        self._synopsis_full: str = ""
        self._quality_rows: List[FormatTableRow] = []
        self._audio_rows: List[FormatTableRow] = []
        self._format_tab: str = TAB_VIDEO
        self._animations_enabled: bool = True
        self._clipboard_last_seen: str = ""

        # Creados antes de conectar señales de combos para _update_size_estimate
        self.lbl_size_estimate = QLabel("")
        self.lbl_size_estimate.setObjectName("SizeEstimate")
        self.lbl_size_note = QLabel("El tamaño es aproximado.")
        self.lbl_size_note.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic;")
        self.lbl_selection_summary = QLabel("")
        self.lbl_selection_summary.setObjectName("DownloadSummary")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(14)

        # ---------------------------------------------------- 1. Encabezado
        self.header_title = QLabel("Analizar contenido")
        self.header_title.setObjectName("ViewTitle")
        self.header_subtitle = QLabel(
            "Pega un enlace y analizamos el contenido para mostrarte las mejores opciones de descarga."
        )
        self.header_subtitle.setObjectName("ViewSubtitle")
        self.header_title.hide()
        self.header_subtitle.hide()
        root.addWidget(self.header_title)
        root.addWidget(self.header_subtitle)

        # --------------------------------------------- 2. Estado vacío (Héroe)
        self.hero_widget = self._build_hero_widget()
        self.hero_wrap = QWidget()
        hero_wrap_layout = QVBoxLayout(self.hero_wrap)
        hero_wrap_layout.setContentsMargins(0, 0, 0, 0)
        hero_wrap_layout.addWidget(self.hero_widget)
        root.addWidget(self.hero_wrap, stretch=1)

        # ------------------------------------- 3. Sugerencia del portapapeles
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

        # ------------------------------ 4. Barra de URL integrada
        self.url_bar = QFrame()
        self.url_bar.setObjectName("UrlBar")
        url_inner = QHBoxLayout(self.url_bar)
        url_inner.setContentsMargins(14, 5, 8, 5)
        url_inner.setSpacing(8)

        search_badge = QLabel()
        search_badge.setPixmap(search_icon(DARK_PALETTE.text_secondary).pixmap(18, 18))
        url_inner.addWidget(search_badge)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText(
            "Pega aquí un enlace de YouTube, TikTok, Instagram o Facebook"
        )
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self._on_analyze_clicked)
        self.url_input.textChanged.connect(self._on_url_edited)
        url_inner.addWidget(self.url_input, stretch=1)

        self.btn_paste = QPushButton("Pegar")
        self.btn_paste.setObjectName("InlineButton")
        self.btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_paste.setToolTip("Pegar desde el portapapeles")
        self.btn_paste.clicked.connect(self._on_paste_clicked)
        url_inner.addWidget(self.btn_paste)

        url_box = QHBoxLayout()
        url_box.setSpacing(12)
        url_box.addWidget(self.url_bar, stretch=1)

        self.btn_analyze = QPushButton("Analizar")
        self.btn_analyze.setObjectName("PrimaryButton")
        self.btn_analyze.setMinimumWidth(110)
        self.btn_analyze.setMinimumHeight(42)
        self.btn_analyze.clicked.connect(self._on_analyze_clicked)
        url_box.addWidget(self.btn_analyze)

        self.btn_batch = QPushButton("Lote...")
        self.btn_batch.setObjectName("SecondaryButton")
        self.btn_batch.setToolTip("Descarga masiva de múltiples URLs")
        self.btn_batch.setMinimumWidth(90)
        self.btn_batch.setMinimumHeight(42)
        self.btn_batch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_batch.clicked.connect(self.batch_requested.emit)
        url_box.addWidget(self.btn_batch)

        root.addLayout(url_box)

        # Banner de estado (vacío / analizando / éxito / error)
        self.lbl_status = QLabel(self.TEXT_EMPTY)
        self.lbl_status.setObjectName("StatusLabel")
        self.lbl_status.setProperty("state", self.STATE_EMPTY)
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        # Indicador de análisis: barra indeterminada
        self.analyzing_bar = QProgressBar()
        self.analyzing_bar.setObjectName("AnalyzingBar")
        self.analyzing_bar.setRange(0, 0)
        self.analyzing_bar.setTextVisible(False)
        self.analyzing_bar.hide()
        root.addWidget(self.analyzing_bar)

        # --------------------------- 5. Área de contenido analizado (Scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setObjectName("InicioScrollArea")
        self.scroll_area.hide()

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(14)

        # 5.1 Card de previsualización modular
        self.preview_card = ContentPreviewCard()
        self.preview_card.hide()
        # Aliases retrocompatibles para tests unitarios y e2e
        self.thumbnail = self.preview_card.thumbnail
        self.lbl_duration_badge = self.preview_card.lbl_duration_badge
        self.thumb_wrap = self.preview_card.thumb_wrap
        self.chip_platform = self.preview_card.chip_platform
        self.chip_duration = self.preview_card.chip_duration
        self.chip_year = self.preview_card.chip_year
        self.chip_quality = self.preview_card.chip_quality
        self.lbl_title = self.preview_card.lbl_title
        self.lbl_channel = self.preview_card.lbl_channel
        self.lbl_synopsis = self.preview_card.lbl_synopsis
        self.btn_toggle_synopsis = self.preview_card.btn_toggle_synopsis
        scroll_layout.addWidget(self.preview_card)

        # 5.2 Card de opciones de formato
        self.format_card = QFrame()
        self.format_card.setObjectName("Card")
        format_card_layout = QVBoxLayout(self.format_card)
        format_card_layout.setContentsMargins(20, 16, 20, 16)
        format_card_layout.setSpacing(12)

        lbl_format_header = QLabel("OPCIONES DE DESCARGA")
        lbl_format_header.setObjectName("SectionHeader")
        format_card_layout.addWidget(lbl_format_header)

        # Tabs de formato
        segment_container = QWidget()
        segment_container.setObjectName("SegmentContainer")
        segment_container.setFixedHeight(42)
        seg_layout = QHBoxLayout(segment_container)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(4)

        self.btn_format_video = QPushButton("▶ Vídeo")
        self.btn_format_audio = QPushButton("♪ Audio")
        self.btn_format_recommended = QPushButton("★ Recomendado")
        for btn in (self.btn_format_video, self.btn_format_audio, self.btn_format_recommended):
            btn.setObjectName("SegmentButton")
            btn.setCheckable(True)
            seg_layout.addWidget(btn)
        seg_layout.addStretch()

        format_nav_row = QHBoxLayout()
        format_nav_row.addWidget(segment_container)
        format_nav_row.addStretch()
        format_card_layout.addLayout(format_nav_row)

        self.format_button_group = QButtonGroup(self)
        self.format_button_group.setExclusive(True)
        self.format_button_group.addButton(self.btn_format_video)
        self.format_button_group.addButton(self.btn_format_audio)
        self.format_button_group.addButton(self.btn_format_recommended)
        self.btn_format_video.setChecked(True)

        # Cabecera de la tabla de formatos
        self.table_header = FormatTableHeader()
        format_card_layout.addWidget(self.table_header)

        # Contenedor de filas de formato
        self.quality_container = QWidget()
        self.quality_layout = QVBoxLayout(self.quality_container)
        self.quality_layout.setContentsMargins(0, 0, 0, 0)
        self.quality_layout.setSpacing(6)
        format_card_layout.addWidget(self.quality_container)

        self.lbl_format_hint = QLabel("")
        self.lbl_format_hint.setObjectName("HintLabel")
        self.lbl_format_hint.setWordWrap(True)
        self.lbl_format_hint.hide()
        format_card_layout.addWidget(self.lbl_format_hint)

        self.quality_button_group = QButtonGroup(self)
        self.quality_button_group.setExclusive(True)
        self.audio_button_group = QButtonGroup(self)
        self.audio_button_group.setExclusive(True)

        # Panel de conversión AUDIO
        self.panel_audio = QWidget()
        self.panel_audio.hide()
        a_layout = QHBoxLayout(self.panel_audio)
        a_layout.setContentsMargins(0, 4, 0, 4)
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
        format_card_layout.addWidget(self.panel_audio)
        format_card_layout.addWidget(self.lbl_audio_note)
        self.lbl_audio_note.hide()

        self.combo_audio_fmt.currentIndexChanged.connect(self._refresh_audio_bitrate_options)
        self.combo_audio_fmt.currentIndexChanged.connect(lambda _: self._update_size_estimate())
        self.combo_audio_br.currentIndexChanged.connect(lambda _: self._update_size_estimate())
        self._refresh_audio_bitrate_options()

        scroll_layout.addWidget(self.format_card)

        # 5.3 Configuración de descarga modular (Carpeta + Nombre editable)
        self.download_config = DownloadConfigWidget()
        self.txt_dest = self.download_config.txt_dest
        self.txt_filename = self.download_config.txt_filename
        scroll_layout.addWidget(self.download_config)

        # 5.4 Barra de acción inferior / Tamaño y Botón Descargar
        self.action_card = QFrame()
        self.action_card.setObjectName("Card")
        action_layout = QHBoxLayout(self.action_card)
        action_layout.setContentsMargins(20, 16, 20, 16)
        action_layout.setSpacing(16)

        size_col = QVBoxLayout()
        size_col.setSpacing(3)
        size_col.addWidget(self.lbl_size_estimate)
        size_col.addWidget(self.lbl_size_note)
        size_col.addWidget(self.lbl_selection_summary)
        action_layout.addLayout(size_col, stretch=1)

        self.btn_download = QPushButton("Iniciar descarga")
        self.btn_download.setObjectName("DownloadButton")
        self.btn_download.setIcon(download_icon(DARK_PALETTE.text_on_accent))
        self.btn_download.setIconSize(QSize(20, 20))
        self.btn_download.setMinimumHeight(50)
        self.btn_download.setMinimumWidth(210)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self._on_download_clicked)
        action_layout.addWidget(self.btn_download)

        scroll_layout.addWidget(self.action_card)

        self.scroll_area.setWidget(scroll_content)
        root.addWidget(self.scroll_area, stretch=1)

        # Conexiones de pestañas
        self.btn_format_recommended.toggled.connect(lambda _: self._on_format_tab_toggled())
        self.btn_format_video.toggled.connect(lambda _: self._on_format_tab_toggled())
        self.btn_format_audio.toggled.connect(lambda _: self._on_format_tab_toggled())

        # Timers de validación de URL y portapapeles
        self._url_validate_timer = QTimer(self)
        self._url_validate_timer.setSingleShot(True)
        self._url_validate_timer.setInterval(URL_VALIDATION_DELAY_MS)
        self._url_validate_timer.timeout.connect(self._validate_url_now)

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
            self.analyzing_bar.show()
            self._set_state_banner(self.STATE_ANALYZING, self.TEXT_ANALYZING)
            self._show_header(show=True)
            self.hero_wrap.hide()
            self.preview_card.hide()
            self.scroll_area.hide()
        else:
            self.btn_analyze.setEnabled(True)
            self.btn_analyze.setText("Analizar")
            self.url_input.setEnabled(True)
            self.analyzing_bar.hide()
            if self.current_metadata is not None:
                self._set_state_banner(self.STATE_SUCCESS, self.TEXT_SUCCESS)
                self._show_header(show=True)
            else:
                self._set_state_banner(self.STATE_EMPTY, self.TEXT_EMPTY)
                self._show_header(show=False)
                self.hero_wrap.show()

    def _show_header(self, show: bool) -> None:
        self.header_title.setVisible(show)
        self.header_subtitle.setVisible(show)

    def show_error(self, message: str) -> None:
        self.current_metadata = None
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Analizar")
        self.url_input.setEnabled(True)
        self.preview_card.hide()
        self.scroll_area.hide()
        self.hero_wrap.hide()
        self.analyzing_bar.hide()
        self._show_header(show=True)
        detail = self._sanitize_error_message(message)
        text = f"{self.TEXT_ERROR_TITLE}. {self.TEXT_ERROR_DETAIL}"
        if detail:
            text = f"{text}\n{detail}"
        self._set_state_banner(self.STATE_ERROR, text)

    @staticmethod
    def _sanitize_error_message(message: str) -> str:
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
        url_str = self._sanitize_input_url(self.url_input.text())
        if url_str:
            self.clipboard_banner.hide()
            self.analyze_requested.emit(url_str)

    # -------------------------------------------------- URL: pegar y validar
    @staticmethod
    def _sanitize_input_url(raw: str) -> str:
        return sanitize_single_video_url((raw or "").strip())

    def _on_paste_clicked(self) -> None:
        clipboard_text = QApplication.clipboard().text().strip()
        if clipboard_text:
            self.url_input.setText(self._sanitize_input_url(clipboard_text))
            self.url_input.setFocus()
            self.url_input.end(False)

    def _on_url_edited(self, text: str) -> None:
        self.clipboard_banner.hide()
        self._url_validate_timer.start()

    def _validate_url_now(self) -> None:
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
        for target in (self.url_input, self.url_bar):
            for prop in ("valid", "invalid"):
                target.setProperty(prop, False)
            if state in ("valid", "invalid"):
                target.setProperty(state, True)
        self.url_input.setToolTip(tooltip)
        style = self.style()
        if style is not None:
            for target in (self.url_input, self.url_bar):
                style.unpolish(target)
                style.polish(target)

    # ------------------------------------------------------------ Portapapeles
    def _poll_clipboard(self) -> None:
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
        candidate = self._sanitize_input_url(self._clipboard_last_seen)
        if candidate:
            self.url_input.setText(candidate)
            self._on_analyze_clicked()

    # ------------------------------------------------------- Previsualización
    def set_metadata(self, metadata: MediaMetadata) -> None:
        self.current_metadata = metadata
        self._synopsis_full = metadata.description or ""
        self.set_analyzing_state(False)

        # Cargar tarjeta de preview
        self.preview_card.set_metadata(metadata)

        # Cargar sugerencia de nombre de archivo editable
        self.download_config.set_suggested_title(metadata.title)

        # Reconstruir opciones de formato
        self._rebuild_quality_options(metadata)

        if not self._quality_rows and metadata.audio_formats:
            self.btn_format_audio.setChecked(True)
        elif metadata.video_quality_options or metadata.video_formats:
            self.btn_format_video.setChecked(True)

        self._update_size_estimate()
        self._update_download_availability()
        self.hero_wrap.hide()
        self._show_header(show=True)
        self.preview_card.show()
        self.scroll_area.show()
        fade_in(self.scroll_area, enabled=self._animations_enabled)

    # --------------------------------------------------------- Filas UI
    def _current_tab(self) -> str:
        if self.btn_format_recommended.isChecked():
            return TAB_RECOMMENDED
        if self.btn_format_audio.isChecked():
            return TAB_AUDIO
        return TAB_VIDEO

    def _on_format_tab_toggled(self) -> None:
        self._format_tab = self._current_tab()
        audio_visible = self._format_tab == TAB_AUDIO
        self.panel_audio.setVisible(audio_visible)
        self.lbl_audio_note.setVisible(audio_visible)
        if self._format_tab == TAB_RECOMMENDED:
            self.selected_type = DownloadType.VIDEO
        elif audio_visible:
            self.selected_type = DownloadType.AUDIO
        else:
            self.selected_type = DownloadType.VIDEO

        if self.current_metadata is not None:
            self._rebuild_quality_options(self.current_metadata)
        else:
            self._update_download_availability()

    def _clear_format_rows(self) -> None:
        while self.quality_layout.count():
            item = self.quality_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if isinstance(widget, FormatTableRow):
                    self.quality_button_group.removeButton(widget.radio)
                    self.audio_button_group.removeButton(widget.radio)
                if widget is not None:
                    widget.deleteLater()
        self._quality_rows.clear()
        self._audio_rows.clear()
        self.quality_container.update()

    def _rebuild_quality_options(self, metadata: MediaMetadata) -> None:
        self._clear_format_rows()

        rows: List[FormatTableRow] = []
        if self._format_tab == TAB_AUDIO:
            rows = [FormatTableRow(af=af) for af in metadata.audio_formats]
        else:
            options = list(metadata.video_quality_options)
            if not options and metadata.video_formats:
                options = self._fallback_quality_options(metadata)
            if self._format_tab == TAB_RECOMMENDED:
                best = [o for o in options if o.is_best_quality]
                chosen = best[:1] or options[:1]
                rows = [FormatTableRow(vqo=o, is_recommended=True) for o in chosen]
                if metadata.audio_formats:
                    rows.append(FormatTableRow(af=metadata.audio_formats[0]))
            else:
                for idx, o in enumerate(options):
                    is_rec = idx == 0 and o.is_best_quality
                    rows.append(FormatTableRow(vqo=o, is_recommended=is_rec))

        for row in rows:
            if row.kind == "video":
                self._quality_rows.append(row)
                self.quality_button_group.addButton(row.radio)
            else:
                self._audio_rows.append(row)
                self.audio_button_group.addButton(row.radio)

            self.quality_layout.addWidget(row)
            row.radio.toggled.connect(
                lambda checked, r=row: self._on_quality_selected(r) if checked else None
            )
            row.btn_download.clicked.connect(lambda _, r=row: self._dispatch_row_download(r))

        if rows:
            self.table_header.show()
            self.quality_container.show()
            self.lbl_format_hint.hide()
            first_row = next((r for r in rows if r.kind == "video"), rows[0])
            if first_row is not None:
                first_row.radio.setChecked(True)
        else:
            self.table_header.hide()
            self.quality_container.hide()
            self.lbl_format_hint.setText(
                self.TEXT_NO_AUDIO if self._format_tab == TAB_AUDIO else self.TEXT_NO_VIDEO_QUALITIES
            )
            self.lbl_format_hint.show()

        self._update_download_availability()

    def _update_download_availability(self) -> None:
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
    def _fallback_quality_options(metadata: MediaMetadata) -> List[VideoQualityOption]:
        options: List[VideoQualityOption] = []
        for vf in metadata.video_formats:
            if not vf.height or vf.is_best_quality:
                continue
            badge = ""
            if vf.height >= 2160:
                badge = "4K"
            elif vf.height >= 1440:
                badge = "2K"
            elif vf.height >= 720:
                badge = "HD"
            elif vf.height >= 480:
                badge = "SD"
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

    def _iter_quality_rows(self) -> List[FormatTableRow]:
        """Filas de VIDEO visibles en la pestaña actual (compatibilidad tests/e2e)."""
        return list(self._quality_rows)

    def _on_quality_selected(self, row: FormatTableRow) -> None:
        self._update_size_estimate()

    def set_default_download_dir(self, path: str) -> None:
        """Actualiza la carpeta de descarga por defecto en el widget de configuración."""
        if hasattr(self, "download_config"):
            self.download_config.set_destination_directory(path)

    def _set_download_mode(self, mode: DownloadType) -> None:
        self.selected_type = mode
        if mode == DownloadType.VIDEO:
            self.btn_format_video.setChecked(True)
        else:
            self.btn_format_audio.setChecked(True)
        self._on_format_tab_toggled()

    def _refresh_audio_bitrate_options(self) -> None:
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
        else:  # wav: sin compresión
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

    def _validated_dest_dir(self) -> Optional[str]:
        dest_dir = self.txt_dest.text().strip()
        if not os.path.isdir(dest_dir):
            self._show_warning("Ruta Inválida", "La carpeta de destino no existe o no es válida.")
            return None
        return dest_dir

    @staticmethod
    def _build_video_request(vqo: VideoQualityOption, title: str = "{title}") -> tuple[str, str]:
        if vqo.is_best_quality:
            return "vq_best", f"{title} - Mejor calidad.mp4"
        return f"vq_{vqo.height}", f"{title} - {vqo.height}p.mp4"

    def _get_clean_base_title(self) -> str:
        """Obtiene el nombre base sanitizado del campo editable o del título original."""
        raw_custom = self.txt_filename.text().strip() if hasattr(self, "txt_filename") else ""
        if not raw_custom and self.current_metadata:
            raw_custom = self.current_metadata.title or "descarga"
        cleaned = self._sanitize_filename(raw_custom)
        for ext in (".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".wav"):
            if cleaned.lower().endswith(ext):
                cleaned = cleaned[:-len(ext)].strip()
                break
        return cleaned or "descarga"

    def _dispatch_row_download(self, row: FormatTableRow) -> None:
        """Despacho directo desde el botón de la fila."""
        if self.current_metadata is None:
            return
        dest_dir = self._validated_dest_dir()
        if not dest_dir:
            return
        title = self._get_clean_base_title()

        if row.kind == "video":
            assert row.vqo is not None
            fmt_id, filename = self._build_video_request(row.vqo)
            filename = filename.format(title=title)
            row.radio.setChecked(True)
        else:
            assert row.af is not None
            af = row.af
            bitrate = max(64, int(round(float(af.bitrate_kbps)))) if af.bitrate_kbps else 128
            fmt_id = f"audio_{af.format_id}_{af.extension}_{bitrate}"
            filename = f"{title} - {bitrate} kbps.{af.extension}"

        dest_path = os.path.join(dest_dir, filename)
        self.download_requested.emit(self.current_metadata, fmt_id, dest_path)

    def _on_download_clicked(self) -> None:
        if not self.current_metadata:
            return

        if not self.btn_download.isEnabled():
            return

        dest_dir = self._validated_dest_dir()
        if not dest_dir:
            return

        title = self._get_clean_base_title()

        if self.selected_type == DownloadType.VIDEO:
            vqo = self._selected_quality_option()
            if vqo is None:
                self.lbl_selection_summary.setText(self.TEXT_NO_VIDEO_QUALITIES)
                return
            fmt_id, filename = self._build_video_request(vqo)
            filename = filename.format(title=title)
        else:
            target_fmt = str(self.combo_audio_fmt.currentData())
            target_br = int(self.combo_audio_br.currentData())
            best_af = self.current_metadata.audio_formats[0] if self.current_metadata.audio_formats else None
            af_id = best_af.format_id if best_af else "best_audio"
            fmt_id = f"audio_{af_id}_{target_fmt}_{target_br}"
            filename = f"{title}.{target_fmt}"

        dest_path = os.path.join(dest_dir, filename)

        # Feedback visual en el botón
        self.btn_download.setText("Iniciando descarga…")
        self.btn_download.setEnabled(False)
        QTimer.singleShot(1400, lambda: self.btn_download.setText("Iniciar descarga"))
        QTimer.singleShot(1400, self._update_download_availability)

        self.download_requested.emit(self.current_metadata, fmt_id, dest_path)

    def _show_warning(self, title: str, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, title, message)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitiza un nombre de archivo eliminando caracteres peligrosos en Windows."""
        return sanitize_filename(name)
