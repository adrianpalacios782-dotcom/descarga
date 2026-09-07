"""Selector interactivo de recorte de tiempo (Lossless Time-Clipper).

Permite al usuario seleccionar un intervalo exacto (inicio y fin) de vídeo o audio
mediante editores numéricos sincronizados, slider dual interactivo y chips de presets rápidos,
acelerando la descarga con yt-dlp (--download-sections) y FFmpeg.
"""

from typing import Optional
import math

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.value_objects.time_range import TimeRange
from src.presentation.styles.theme import get_current_palette


class DualRangeSlider(QWidget):
    """Slider interactivo con dos controles deslizantes (inicio y fin) sobre una pista compartida."""

    rangeChanged = Signal(float, float)

    def __init__(
        self,
        min_val: float = 0.0,
        max_val: float = 100.0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DualRangeSlider")
        self.setMinimumHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._min_val: float = max(0.0, min_val)
        self._max_val: float = max(self._min_val + 1.0, max_val)
        self._start_val: float = self._min_val
        self._end_val: float = self._max_val

        self._handle_radius: float = 8.0
        self._active_handle: Optional[str] = None  # "start" | "end" | None

    # ------------------------------------------------------------- Propiedades
    def set_range(self, min_val: float, max_val: float) -> None:
        self._min_val = max(0.0, min_val)
        self._max_val = max(self._min_val + 1.0, max_val)
        self._start_val = max(self._min_val, min(self._start_val, self._max_val - 0.5))
        self._end_val = min(self._max_val, max(self._end_val, self._start_val + 0.5))
        self.update()

    def set_values(self, start_val: float, end_val: float) -> None:
        clamped_start = max(self._min_val, min(start_val, self._max_val - 0.1))
        clamped_end = min(self._max_val, max(end_val, clamped_start + 0.1))
        if abs(self._start_val - clamped_start) > 0.01 or abs(self._end_val - clamped_end) > 0.01:
            self._start_val = clamped_start
            self._end_val = clamped_end
            self.update()

    @property
    def start_val(self) -> float:
        return self._start_val

    @property
    def end_val(self) -> float:
        return self._end_val

    # ----------------------------------------------------------- Coordenadas
    def _val_to_x(self, val: float, track_left: float, track_width: float) -> float:
        span = max(1.0, self._max_val - self._min_val)
        pct = (val - self._min_val) / span
        return track_left + pct * track_width

    def _x_to_val(self, x: float, track_left: float, track_width: float) -> float:
        if track_width <= 0:
            return self._min_val
        pct = max(0.0, min(1.0, (x - track_left) / track_width))
        span = max(1.0, self._max_val - self._min_val)
        return self._min_val + pct * span

    # --------------------------------------------------------------- Pintado
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        p = get_current_palette()
        w = float(self.width())
        h = float(self.height())
        margin = self._handle_radius + 4.0
        track_left = margin
        track_width = max(10.0, w - (margin * 2.0))
        track_height = 6.0
        track_y = (h - track_height) / 2.0

        # Pista inactiva de fondo
        bg_track_color = QColor(p.surface_sunken)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_track_color)
        painter.drawRoundedRect(
            QRectF(track_left, track_y, track_width, track_height),
            track_height / 2.0,
            track_height / 2.0,
        )

        # Segmento seleccionado activo
        start_x = self._val_to_x(self._start_val, track_left, track_width)
        end_x = self._val_to_x(self._end_val, track_left, track_width)
        slice_width = max(2.0, end_x - start_x)

        accent_color = QColor(p.accent)
        painter.setBrush(accent_color)
        painter.drawRoundedRect(
            QRectF(start_x, track_y, slice_width, track_height),
            track_height / 2.0,
            track_height / 2.0,
        )

        # Tirador de Inicio
        handle_center_y = h / 2.0
        handle_pen = QPen(QColor(p.accent), 2.0)
        handle_brush = QColor(p.surface)

        painter.setPen(handle_pen)
        painter.setBrush(handle_brush)
        painter.drawEllipse(
            QPoint(int(round(start_x)), int(round(handle_center_y))),
            int(self._handle_radius),
            int(self._handle_radius),
        )

        # Tirador de Fin
        painter.drawEllipse(
            QPoint(int(round(end_x)), int(round(handle_center_y))),
            int(self._handle_radius),
            int(self._handle_radius),
        )

        painter.end()

    # --------------------------------------------------------- Eventos Ratón
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        w = float(self.width())
        margin = self._handle_radius + 4.0
        track_left = margin
        track_width = max(10.0, w - (margin * 2.0))

        click_x = float(event.position().x())
        start_x = self._val_to_x(self._start_val, track_left, track_width)
        end_x = self._val_to_x(self._end_val, track_left, track_width)

        dist_start = abs(click_x - start_x)
        dist_end = abs(click_x - end_x)

        # Si el click está cerca del tirador o en la pista
        if dist_start <= dist_end:
            self._active_handle = "start"
            new_val = self._x_to_val(click_x, track_left, track_width)
            self._start_val = max(self._min_val, min(new_val, self._end_val - 0.5))
        else:
            self._active_handle = "end"
            new_val = self._x_to_val(click_x, track_left, track_width)
            self._end_val = min(self._max_val, max(new_val, self._start_val + 0.5))

        self.update()
        self.rangeChanged.emit(self._start_val, self._end_val)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._active_handle:
            return

        w = float(self.width())
        margin = self._handle_radius + 4.0
        track_left = margin
        track_width = max(10.0, w - (margin * 2.0))

        cur_x = float(event.position().x())
        new_val = self._x_to_val(cur_x, track_left, track_width)

        if self._active_handle == "start":
            self._start_val = max(self._min_val, min(new_val, self._end_val - 0.5))
        elif self._active_handle == "end":
            self._end_val = min(self._max_val, max(new_val, self._start_val + 0.5))

        self.update()
        self.rangeChanged.emit(self._start_val, self._end_val)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._active_handle = None


class TimeRangeSelectorWidget(QFrame):
    """Widget de recorte de tiempo en vivo con slider dual y sincronización de entradas."""

    timeRangeChanged = Signal(object)  # Optional[TimeRange]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("TimeRangeSelectorCard")

        self._total_duration: float = 0.0
        self._updating_from_code: bool = False

        self._init_ui()
        self._apply_theme()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # 1. Cabecera con CheckBox toggle
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.chk_enable = QCheckBox("Recortar segmento de tiempo (descarga rápida)")
        self.chk_enable.setObjectName("TimeRangeToggle")
        self.chk_enable.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_enable.toggled.connect(self._on_toggle_toggled)

        self.lbl_mode_badge = QLabel("⚡ Lossless")
        self.lbl_mode_badge.setObjectName("LosslessBadge")
        self.lbl_mode_badge.setStyleSheet(
            "background: rgba(14, 165, 233, 0.15); color: #0EA5E9; "
            "padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;"
        )

        header_row.addWidget(self.chk_enable)
        header_row.addWidget(self.lbl_mode_badge)
        header_row.addStretch()
        layout.addLayout(header_row)

        # 2. Contenedor de controles de recorte
        self.body_container = QWidget()
        body_layout = QVBoxLayout(self.body_container)
        body_layout.setContentsMargins(0, 4, 0, 0)
        body_layout.setSpacing(10)

        # 2.1 Entradas de tiempo numéricas y duración calculada
        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(12)

        lbl_start = QLabel("Inicio:")
        lbl_start.setObjectName("FieldLabel")
        self.input_start = QLineEdit("00:00:00")
        self.input_start.setObjectName("TimeInput")
        self.input_start.setFixedHeight(34)
        self.input_start.setMaximumWidth(110)
        self.input_start.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_start.editingFinished.connect(self._on_input_changed)

        lbl_end = QLabel("Fin:")
        lbl_end.setObjectName("FieldLabel")
        self.input_end = QLineEdit("00:00:00")
        self.input_end.setObjectName("TimeInput")
        self.input_end.setFixedHeight(34)
        self.input_end.setMaximumWidth(110)
        self.input_end.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_end.editingFinished.connect(self._on_input_changed)

        self.lbl_clip_duration = QLabel("Duración del clip: 00:00:00")
        self.lbl_clip_duration.setObjectName("ClipDurationLabel")
        self.lbl_clip_duration.setStyleSheet("font-weight: 600; font-size: 12px;")

        inputs_row.addWidget(lbl_start)
        inputs_row.addWidget(self.input_start)
        inputs_row.addWidget(lbl_end)
        inputs_row.addWidget(self.input_end)
        inputs_row.addSpacing(8)
        inputs_row.addWidget(self.lbl_clip_duration)
        inputs_row.addStretch()
        body_layout.addLayout(inputs_row)

        # 2.2 Slider Dual Interactivo
        slider_box = QVBoxLayout()
        slider_box.setSpacing(3)

        self.slider = DualRangeSlider(min_val=0.0, max_val=100.0)
        self.slider.rangeChanged.connect(self._on_slider_range_changed)
        slider_box.addWidget(self.slider)

        # Etiquetas de límite temporal debajo del slider
        limits_row = QHBoxLayout()
        self.lbl_slider_min = QLabel("00:00:00")
        self.lbl_slider_min.setStyleSheet("color: #64748B; font-size: 11px;")
        self.lbl_slider_max = QLabel("00:00:00")
        self.lbl_slider_max.setStyleSheet("color: #64748B; font-size: 11px;")

        limits_row.addWidget(self.lbl_slider_min)
        limits_row.addStretch()
        limits_row.addWidget(self.lbl_slider_max)
        slider_box.addLayout(limits_row)
        body_layout.addLayout(slider_box)

        # 2.3 Chips de Presets Rápidos
        presets_row = QHBoxLayout()
        presets_row.setSpacing(8)

        lbl_presets = QLabel("Presets rápidos:")
        lbl_presets.setObjectName("HintLabel")
        lbl_presets.setStyleSheet("color: #64748B; font-size: 11px;")
        presets_row.addWidget(lbl_presets)

        self.btn_preset_first_min = self._make_preset_chip("Primer minuto", self._apply_first_min)
        self.btn_preset_last_30s = self._make_preset_chip("Últimos 30s", self._apply_last_30s)
        self.btn_preset_clip_1m = self._make_preset_chip("Clip de 1 min", self._apply_clip_1m)
        self.btn_preset_reset = self._make_preset_chip("Restablecer todo", self._apply_reset_all)

        presets_row.addWidget(self.btn_preset_first_min)
        presets_row.addWidget(self.btn_preset_last_30s)
        presets_row.addWidget(self.btn_preset_clip_1m)
        presets_row.addWidget(self.btn_preset_reset)
        presets_row.addStretch()
        body_layout.addLayout(presets_row)

        # 2.4 Etiqueta de validación visual inline
        self.lbl_validation = QLabel("")
        self.lbl_validation.setObjectName("ValidationLabel")
        self.lbl_validation.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: 500;")
        self.lbl_validation.hide()
        body_layout.addWidget(self.lbl_validation)

        layout.addWidget(self.body_container)

        # Inicia contraído/deshabilitado
        self.body_container.hide()

    def _make_preset_chip(self, label: str, slot: object) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("PresetChipButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(26)
        if callable(slot):
            btn.clicked.connect(slot)
        return btn

    # ------------------------------------------------------------- Estilos
    def _apply_theme(self) -> None:
        if getattr(self, "_applying_theme", False):
            return
        self._applying_theme = True
        try:
            p = get_current_palette()
            self.setStyleSheet(
                f"""
                QFrame#TimeRangeSelectorCard {{
                    background-color: {p.surface};
                    border: 1px solid {p.border};
                    border-radius: 12px;
                }}
                QCheckBox#TimeRangeToggle {{
                    color: {p.text_primary};
                    font-weight: 600;
                    font-size: 13px;
                    spacing: 8px;
                }}
                QLineEdit#TimeInput {{
                    background-color: {p.surface_sunken};
                    color: {p.text_primary};
                    border: 1px solid {p.border_strong};
                    border-radius: 8px;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 12px;
                    font-weight: 500;
                    padding: 0 8px;
                }}
                QLineEdit#TimeInput:focus {{
                    border: 1px solid {p.border_focus};
                }}
                QPushButton#PresetChipButton {{
                    background-color: {p.surface_hover};
                    color: {p.text_secondary};
                    border: 1px solid {p.border};
                    border-radius: 13px;
                    padding: 0 10px;
                    font-size: 11px;
                }}
                QPushButton#PresetChipButton:hover {{
                    background-color: {p.accent_dim};
                    color: {p.accent};
                    border-color: {p.accent};
                }}
                """
            )
            self.slider.update()
        finally:
            self._applying_theme = False

    def changeEvent(self, event: QEvent) -> None:
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self._apply_theme()
        super().changeEvent(event)

    # -------------------------------------------------- Métodos Públicos API
    def set_total_duration(self, duration_seconds: float) -> None:
        """Configura la duración total del medio para calibrar los límites del recorte."""
        self._total_duration = max(0.0, float(duration_seconds))
        formatted_total = TimeRange.format_seconds(self._total_duration)
        self.lbl_slider_max.setText(formatted_total)

        if self._total_duration > 0:
            self.slider.set_range(0.0, self._total_duration)
            self._set_ui_values(0.0, self._total_duration)
        else:
            self.slider.set_range(0.0, 100.0)
            self._set_ui_values(0.0, 0.0)

    def get_time_range(self) -> Optional[TimeRange]:
        """Retorna el TimeRange validado si el recorte está activo, o None."""
        if not self.chk_enable.isChecked() or not self.is_valid():
            return None

        try:
            start_sec = TimeRange.parse_timestamp(self.input_start.text())
            end_sec = TimeRange.parse_timestamp(self.input_end.text())
            if end_sec <= start_sec:
                return None
            return TimeRange(start_seconds=start_sec, end_seconds=end_sec)
        except Exception:
            return None

    def set_time_range(self, time_range: Optional[TimeRange]) -> None:
        """Establece programáticamente el intervalo de recorte."""
        if not time_range:
            self.chk_enable.setChecked(False)
            return

        self.chk_enable.setChecked(True)
        end_val = time_range.end_seconds if time_range.end_seconds is not None else self._total_duration
        self._set_ui_values(time_range.start_seconds, end_val)

    def is_enabled(self) -> bool:
        return self.chk_enable.isChecked()

    def is_valid(self) -> bool:
        try:
            start_sec = TimeRange.parse_timestamp(self.input_start.text())
            end_sec = TimeRange.parse_timestamp(self.input_end.text())
            return start_sec >= 0.0 and end_sec > start_sec
        except Exception:
            return False

    def reset(self) -> None:
        self.chk_enable.setChecked(False)
        self.set_total_duration(0.0)

    # --------------------------------------------------------- Sincronización
    def _set_ui_values(self, start_sec: float, end_sec: float) -> None:
        self._updating_from_code = True
        try:
            clamped_start = max(0.0, start_sec)
            clamped_end = max(clamped_start + 0.1, end_sec)
            self.input_start.setText(TimeRange.format_seconds(clamped_start))
            self.input_end.setText(TimeRange.format_seconds(clamped_end))
            self.slider.set_values(clamped_start, clamped_end)
            self._update_clip_duration_label(clamped_start, clamped_end)
            self._validate_ui()
        finally:
            self._updating_from_code = False
            self.timeRangeChanged.emit(self.get_time_range())

    def _on_toggle_toggled(self, checked: bool) -> None:
        self.body_container.setVisible(checked)
        if checked and self._total_duration > 0:
            cur_end = self.slider.end_val
            if cur_end <= 0:
                self._set_ui_values(0.0, self._total_duration)
        self.timeRangeChanged.emit(self.get_time_range())

    def _on_slider_range_changed(self, start_val: float, end_val: float) -> None:
        if self._updating_from_code:
            return
        self._updating_from_code = True
        try:
            self.input_start.setText(TimeRange.format_seconds(start_val))
            self.input_end.setText(TimeRange.format_seconds(end_val))
            self._update_clip_duration_label(start_val, end_val)
            self._validate_ui()
        finally:
            self._updating_from_code = False
            self.timeRangeChanged.emit(self.get_time_range())

    def _on_input_changed(self) -> None:
        if self._updating_from_code:
            return
        try:
            start_sec = TimeRange.parse_timestamp(self.input_start.text())
            end_sec = TimeRange.parse_timestamp(self.input_end.text())
            self.slider.set_values(start_sec, end_sec)
            self._update_clip_duration_label(start_sec, end_sec)
            self._validate_ui()
            self.timeRangeChanged.emit(self.get_time_range())
        except Exception:
            self._validate_ui()

    def _update_clip_duration_label(self, start_sec: float, end_sec: float) -> None:
        diff = max(0.0, end_sec - start_sec)
        diff_str = TimeRange.format_seconds(diff)
        pct_text = ""
        if self._total_duration > 0:
            pct = min(100.0, max(0.0, (diff / self._total_duration) * 100.0))
            pct_text = f" ({math.ceil(pct)}% del total)"
        self.lbl_clip_duration.setText(f"Duración del clip: {diff_str}{pct_text}")

    def _validate_ui(self) -> None:
        valid = self.is_valid()
        p = get_current_palette()
        if not valid:
            self.input_start.setStyleSheet("border: 1px solid #EF4444; border-radius: 8px;")
            self.input_end.setStyleSheet("border: 1px solid #EF4444; border-radius: 8px;")
            self.lbl_validation.setText("El tiempo de inicio debe ser estrictamente menor que el tiempo final.")
            self.lbl_validation.show()
        else:
            self.input_start.setStyleSheet(
                f"background-color: {p.surface_sunken}; color: {p.text_primary}; "
                f"border: 1px solid {p.border_strong}; border-radius: 8px;"
            )
            self.input_end.setStyleSheet(
                f"background-color: {p.surface_sunken}; color: {p.text_primary}; "
                f"border: 1px solid {p.border_strong}; border-radius: 8px;"
            )
            self.lbl_validation.hide()

    # ------------------------------------------------------ Presets Rápidos
    def _apply_first_min(self) -> None:
        end = min(60.0, self._total_duration) if self._total_duration > 0 else 60.0
        self._set_ui_values(0.0, end)

    def _apply_last_30s(self) -> None:
        if self._total_duration > 0:
            start = max(0.0, self._total_duration - 30.0)
            self._set_ui_values(start, self._total_duration)
        else:
            self._set_ui_values(0.0, 30.0)

    def _apply_clip_1m(self) -> None:
        cur_start = self.slider.start_val
        target_end = cur_start + 60.0
        if self._total_duration > 0 and target_end > self._total_duration:
            target_end = self._total_duration
        self._set_ui_values(cur_start, target_end)

    def _apply_reset_all(self) -> None:
        self._set_ui_values(0.0, self._total_duration)
