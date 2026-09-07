import pytest
from PySide6.QtWidgets import QApplication

from src.domain.value_objects.time_range import TimeRange
from src.presentation.components.time_range_selector import (
    DualRangeSlider,
    TimeRangeSelectorWidget,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dual_range_slider_defaults_and_range(qapp):
    slider = DualRangeSlider(min_val=0.0, max_val=120.0)
    assert slider.start_val == 0.0
    assert slider.end_val == 120.0

    slider.set_values(10.0, 50.0)
    assert slider.start_val == 10.0
    assert slider.end_val == 50.0

    # Clamping
    slider.set_values(-5.0, 200.0)
    assert slider.start_val >= 0.0
    assert slider.end_val <= 120.0


def test_time_range_selector_initial_state(qapp):
    widget = TimeRangeSelectorWidget()
    assert not widget.is_enabled()
    assert not widget.body_container.isVisible()
    assert widget.get_time_range() is None


def test_time_range_selector_toggle(qapp):
    widget = TimeRangeSelectorWidget()
    widget.show()
    emitted = []
    widget.timeRangeChanged.connect(lambda tr: emitted.append(tr))

    widget.chk_enable.setChecked(True)
    assert widget.is_enabled()
    assert not widget.body_container.isHidden()

    widget.chk_enable.setChecked(False)
    assert not widget.is_enabled()
    assert widget.body_container.isHidden()
    assert len(emitted) >= 2


def test_time_range_selector_with_duration_and_presets(qapp):
    widget = TimeRangeSelectorWidget()
    widget.show()
    widget.set_total_duration(300.0)  # 5 minutos (00:05:00)

    assert widget.lbl_slider_max.text() == "00:05:00"

    widget.chk_enable.setChecked(True)

    # Preset 1: Primer minuto
    widget.btn_preset_first_min.click()
    tr = widget.get_time_range()
    assert tr is not None
    assert tr.start_seconds == 0.0
    assert tr.end_seconds == 60.0
    assert "00:01:00" in widget.lbl_clip_duration.text()

    # Preset 2: Últimos 30s
    widget.btn_preset_last_30s.click()
    tr2 = widget.get_time_range()
    assert tr2 is not None
    assert tr2.start_seconds == 270.0
    assert tr2.end_seconds == 300.0

    # Preset 3: Restablecer todo
    widget.btn_preset_reset.click()
    tr3 = widget.get_time_range()
    assert tr3 is not None
    assert tr3.start_seconds == 0.0
    assert tr3.end_seconds == 300.0


def test_time_range_selector_validation(qapp):
    widget = TimeRangeSelectorWidget()
    widget.show()
    widget.set_total_duration(120.0)
    widget.chk_enable.setChecked(True)

    # Establecer manualmente valores inválidos (start > end)
    widget.input_start.setText("01:00")
    widget.input_end.setText("00:30")
    widget._on_input_changed()

    assert not widget.is_valid()
    assert not widget.lbl_validation.isHidden()
    assert widget.get_time_range() is None

    # Corregir a valores válidos
    widget.input_end.setText("02:00")
    widget._on_input_changed()

    assert widget.is_valid()
    assert widget.lbl_validation.isHidden()
    tr = widget.get_time_range()
    assert tr is not None
    assert tr.start_seconds == 60.0
    assert tr.end_seconds == 120.0
