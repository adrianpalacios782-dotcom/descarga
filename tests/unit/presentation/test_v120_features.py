import pytest
from PySide6.QtWidgets import QApplication

from src.domain.value_objects.audio_preset import AudioPreset
from src.presentation.components.download_config_widget import DownloadConfigWidget
from src.presentation.view_models.main_view_model import MainViewModel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_download_config_widget_trimming(qapp):
    widget = DownloadConfigWidget()
    assert widget.get_time_range() is None

    widget.chk_trim.setChecked(True)
    widget.txt_start.setText("00:30")
    widget.txt_end.setText("01:45")

    tr = widget.get_time_range()
    assert tr is not None
    assert tr.start_seconds == 30.0
    assert tr.end_seconds == 105.0


def test_download_config_widget_audio_presets(qapp):
    widget = DownloadConfigWidget()
    widget.set_audio_mode(True)
    assert not widget.audio_options_box.isHidden()
    assert widget.get_audio_preset() is not None
    assert widget.get_embed_thumbnail() is True


def test_main_view_model_parse_speed_limit():
    assert MainViewModel._parse_speed_limit("0") is None
    assert MainViewModel._parse_speed_limit("Sin límite") is None
    assert MainViewModel._parse_speed_limit("50M") == 50 * 1024 * 1024
    assert MainViewModel._parse_speed_limit("10MB/s") == 10 * 1024 * 1024
    assert MainViewModel._parse_speed_limit("500K") == 500 * 1024
