import os
from typing import Optional
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFrame, QComboBox, QFileDialog, QMessageBox, QListWidget, QListWidgetItem
)

from src.domain.entities.format_option import DownloadType, FormatOption, VideoFormat, AudioFormat, VideoQualityOption
from src.domain.entities.media_metadata import MediaMetadata


class InicioView(QWidget):
    """Vista principal para ingresar URLs, analizar contenido y seleccionar resolución/formato de descarga."""
    analyze_requested = Signal(str)
    download_requested = Signal(object, str, str)  # (media_metadata, format_id, destination_path)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_metadata: Optional[MediaMetadata] = None
        self.selected_type: DownloadType = DownloadType.VIDEO

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Encabezado
        title = QLabel("Nueva Descarga Multimedia")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        subtitle = QLabel("Pega el enlace de YouTube, TikTok, Instagram o Facebook para obtener el contenido")
        subtitle.setStyleSheet("font-size: 13px; color: #b3b3b3;")
        
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Fila de URL
        url_box = QHBoxLayout()
        url_box.setSpacing(12)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        
        self.btn_analyze = QPushButton("Analizar")
        self.btn_analyze.setObjectName("PrimaryButton")
        self.btn_analyze.clicked.connect(self._on_analyze_clicked)

        url_box.addWidget(self.url_input)
        url_box.addWidget(self.btn_analyze)
        layout.addLayout(url_box)

        # Card de Vista Previa y Selección
        self.preview_card = QFrame()
        self.preview_card.setObjectName("Card")
        self.preview_card.hide()

        card_layout = QVBoxLayout(self.preview_card)
        card_layout.setSpacing(16)

        self.lbl_title = QLabel("Título del Contenido")
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        self.lbl_meta = QLabel("Plataforma — Duración: --:--")
        self.lbl_meta.setStyleSheet("font-size: 13px; color: #b3b3b3;")

        card_layout.addWidget(self.lbl_title)
        card_layout.addWidget(self.lbl_meta)

        # 1. Selector de Tipo de Descarga: [ VIDEO ] vs [ AUDIO ]
        type_layout = QHBoxLayout()
        type_layout.setSpacing(10)
        lbl_type = QLabel("Tipo de Descarga:")
        lbl_type.setStyleSheet("font-size: 13px; font-weight: 700; color: #b3b3b3;")
        
        self.btn_video_mode = QPushButton("VIDEO")
        self.btn_video_mode.setObjectName("ModeButton")
        self.btn_video_mode.setCheckable(True)
        self.btn_video_mode.setChecked(True)
        self.btn_video_mode.clicked.connect(lambda: self._set_download_mode(DownloadType.VIDEO))

        self.btn_audio_mode = QPushButton("AUDIO")
        self.btn_audio_mode.setObjectName("ModeButton")
        self.btn_audio_mode.setCheckable(True)
        self.btn_audio_mode.clicked.connect(lambda: self._set_download_mode(DownloadType.AUDIO))

        type_layout.addWidget(lbl_type)
        type_layout.addWidget(self.btn_video_mode)
        type_layout.addWidget(self.btn_audio_mode)
        type_layout.addStretch()
        card_layout.addLayout(type_layout)

        # 2. Panel de VIDEO (Selector Vertical Limpio de Resoluciones Reales)
        self.panel_video = QWidget()
        v_layout = QVBoxLayout(self.panel_video)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(8)
        
        lbl_v_fmt = QLabel("Calidad de Video:")
        lbl_v_fmt.setStyleSheet("font-size: 13px; font-weight: 600; color: #ffffff;")
        
        self.list_video_quality = QListWidget()
        self.list_video_quality.setObjectName("VideoQualityList")

        v_layout.addWidget(lbl_v_fmt)
        v_layout.addWidget(self.list_video_quality)
        card_layout.addWidget(self.panel_video)

        # 3. Panel de AUDIO (Formato / Bitrate)
        self.panel_audio = QWidget()
        self.panel_audio.hide()
        a_layout = QHBoxLayout(self.panel_audio)
        a_layout.setContentsMargins(0, 0, 0, 0)
        a_layout.setSpacing(12)

        lbl_a_fmt = QLabel("Formato:")
        lbl_a_fmt.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.combo_audio_fmt = QComboBox()
        self.combo_audio_fmt.addItem("MP3", userData="mp3")
        self.combo_audio_fmt.addItem("M4A", userData="m4a")
        self.combo_audio_fmt.addItem("WAV", userData="wav")

        lbl_a_br = QLabel("Bitrate:")
        lbl_a_br.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.combo_audio_br = QComboBox()

        self.lbl_audio_note = QLabel("La conversión mantiene la calidad original del audio; no la aumenta.")
        self.lbl_audio_note.setStyleSheet("font-size: 11px; color: #b3b3b3;")
        self.lbl_audio_note.setWordWrap(True)

        a_layout.addWidget(lbl_a_fmt)
        a_layout.addWidget(self.combo_audio_fmt, stretch=1)
        a_layout.addWidget(lbl_a_br)
        a_layout.addWidget(self.combo_audio_br, stretch=1)
        card_layout.addWidget(self.panel_audio)
        card_layout.addWidget(self.lbl_audio_note)

        self.combo_audio_fmt.currentIndexChanged.connect(self._refresh_audio_bitrate_options)
        self._refresh_audio_bitrate_options()

        # Carpeta de Destino
        dest_layout = QHBoxLayout()
        dest_layout.setSpacing(12)
        lbl_dest = QLabel("Guardar en:")
        lbl_dest.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.txt_dest = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads"))
        btn_browse = QPushButton("Examinar...")
        btn_browse.setObjectName("SecondaryButton")
        btn_browse.clicked.connect(self._on_browse_dest)

        dest_layout.addWidget(lbl_dest)
        dest_layout.addWidget(self.txt_dest, stretch=1)
        dest_layout.addWidget(btn_browse)
        card_layout.addLayout(dest_layout)

        # Botón de Descarga
        self.btn_download = QPushButton("Iniciar Descarga")
        self.btn_download.setObjectName("PrimaryButton")
        self.btn_download.clicked.connect(self._on_download_clicked)
        card_layout.addWidget(self.btn_download)

        layout.addWidget(self.preview_card)
        layout.addStretch()

    def _set_download_mode(self, mode: DownloadType) -> None:
        self.selected_type = mode
        if mode == DownloadType.VIDEO:
            self.btn_video_mode.setChecked(True)
            self.btn_audio_mode.setChecked(False)
            self.panel_video.show()
            self.panel_audio.hide()
        else:
            self.btn_video_mode.setChecked(False)
            self.btn_audio_mode.setChecked(True)
            self.panel_video.hide()
            self.panel_audio.show()

    def set_analyzing_state(self, is_analyzing: bool) -> None:
        if is_analyzing:
            self.btn_analyze.setEnabled(False)
            self.btn_analyze.setText("Analizando...")
            self.url_input.setEnabled(False)
        else:
            self.btn_analyze.setEnabled(True)
            self.btn_analyze.setText("Analizar")
            self.url_input.setEnabled(True)

    def _on_analyze_clicked(self) -> None:
        url_str = self.url_input.text().strip()
        if url_str:
            self.analyze_requested.emit(url_str)

    def set_metadata(self, metadata: MediaMetadata) -> None:
        self.set_analyzing_state(False)
        self.current_metadata = metadata
        self.lbl_title.setText(metadata.title)
        self.lbl_meta.setText(f"Plataforma: {metadata.platform} — Duración: {metadata.get_duration_formatted()} — Autor: {metadata.author}")

        # Poblar opciones de VIDEO verticales limpias (resoluciones reales + "Mejor calidad")
        self.list_video_quality.clear()

        options = metadata.video_quality_options
        if not options and metadata.video_formats:
            options = self._fallback_quality_options(metadata)

        for vqo in options:
            item = QListWidgetItem()
            if vqo.is_best_quality:
                item.setData(Qt.UserRole, "vq_best")
            else:
                item.setData(Qt.UserRole, f"vq_{vqo.height}")

            row_widget = QWidget()
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(12, 4, 12, 4)
            row_layout.setSpacing(2)

            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(8)

            lbl_label = QLabel(vqo.label)
            lbl_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
            top_row.addWidget(lbl_label)

            if vqo.badge:
                lbl_badge = QLabel(vqo.badge)
                lbl_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #000000; background-color: #1db954; padding: 2px 8px; border-radius: 4px;")
                top_row.addWidget(lbl_badge)

            top_row.addStretch()

            lbl_info = QLabel(vqo.get_technical_info())
            lbl_info.setStyleSheet("font-size: 11px; color: #727272;")

            row_layout.addLayout(top_row)
            row_layout.addWidget(lbl_info)

            item.setSizeHint(QSize(0, 56))
            self.list_video_quality.addItem(item)
            self.list_video_quality.setItemWidget(item, row_widget)

        # Ajustar la altura dinámica del QListWidget según el número de ítems
        count = self.list_video_quality.count()
        if count > 0:
            self.list_video_quality.setCurrentRow(0)
            target_height = min(320, max(56, count * 58 + 8))
            self.list_video_quality.setFixedHeight(target_height)

        # Si no hay opciones de video pero sí de audio, cambiar automáticamente a modo AUDIO
        if count == 0 and metadata.audio_formats:
            self._set_download_mode(DownloadType.AUDIO)

        self.preview_card.show()

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

    def show_error(self, message: str) -> None:
        self.set_analyzing_state(False)
        QMessageBox.warning(self, "Error de Análisis", message)

    def _on_browse_dest(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino")
        if directory:
            self.txt_dest.setText(directory)

    def _refresh_audio_bitrate_options(self) -> None:
        """Actualiza los bitrates ofrecidos según el formato de audio seleccionado (honestos y producibles)."""
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

    def _on_download_clicked(self) -> None:
        if not self.current_metadata:
            return

        dest_dir = self.txt_dest.text().strip()
        title = self._sanitize_filename(self.current_metadata.title)

        if self.selected_type == DownloadType.VIDEO:
            current_item = self.list_video_quality.currentItem()
            if not current_item:
                QMessageBox.warning(self, "Selección Requerida", "Por favor selecciona una resolución de video.")
                return
            fmt_id = current_item.data(Qt.UserRole)
            if fmt_id == "vq_best":
                filename = f"{title} - Mejor calidad.mp4"
            else:
                try:
                    height = int(fmt_id.replace("vq_", ""))
                    filename = f"{title} - {height}p.mp4"
                except ValueError:
                    filename = f"{title}.mp4"
        else:
            target_fmt = str(self.combo_audio_fmt.currentData())
            target_br = int(self.combo_audio_br.currentData())
            best_af = self.current_metadata.audio_formats[0] if self.current_metadata.audio_formats else None
            af_id = best_af.format_id if best_af else "best_audio"
            fmt_id = f"audio_{af_id}_{target_fmt}_{target_br}"
            filename = f"{title}.{target_fmt}"

        dest_path = os.path.join(dest_dir, filename)
        self.download_requested.emit(self.current_metadata, fmt_id, dest_path)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        import re
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        cleaned = cleaned.strip().rstrip(".")
        return cleaned[:180] if cleaned else "descarga"
