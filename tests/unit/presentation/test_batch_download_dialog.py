from unittest.mock import patch
import pytest
from PySide6.QtWidgets import QApplication

from src.presentation.components.batch_download_dialog import BatchDownloadDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_batch_download_dialog_init(qapp):
    dlg = BatchDownloadDialog(default_dir="/dummy/dir")
    assert dlg.windowTitle() == "Descarga Masiva por Lotes"
    assert dlg.btn_start.isEnabled() is False
    assert "/dummy/dir" in dlg.txt_dir.text() or "dummy" in dlg.txt_dir.text()


def test_batch_download_dialog_extract_urls(qapp):
    dlg = BatchDownloadDialog()
    raw_text = """
    https://www.youtube.com/watch?v=123
    texto no valido
    http://example.com/video.mp4
       https://tiktok.com/@user/123
    ftp://invalido.com
    """
    dlg.txt_urls.setPlainText(raw_text)

    urls = dlg.extract_urls()
    assert len(urls) == 3
    assert urls[0] == "https://www.youtube.com/watch?v=123"
    assert urls[1] == "http://example.com/video.mp4"
    assert urls[2] == "https://tiktok.com/@user/123"
    assert dlg.btn_start.isEnabled() is True


def test_batch_download_dialog_start_emission(qapp, tmp_path):
    dest_folder = str(tmp_path)
    dlg = BatchDownloadDialog(default_dir=dest_folder)
    dlg.txt_urls.setPlainText("https://www.youtube.com/watch?v=abc\nhttps://www.youtube.com/watch?v=def")

    emitted_data = []
    dlg.batch_requested.connect(lambda u, q, d: emitted_data.append((u, q, d)))

    with patch.object(dlg, "accept"):
        dlg._on_start_clicked()

    assert len(emitted_data) == 1
    urls, quality, ddir = emitted_data[0]
    assert len(urls) == 2
    assert "Mejor" in quality or "1080" in quality
    assert ddir == dest_folder


def test_main_view_model_process_batch(tmp_path):
    from unittest.mock import MagicMock
    from src.domain.entities.format_option import FormatOption, StreamType, DownloadType
    from src.domain.entities.media_metadata import MediaMetadata
    from src.domain.value_objects.media_id import MediaId
    from src.domain.value_objects.url import Url
    from src.presentation.view_models.main_view_model import MainViewModel

    mock_repo = MagicMock()
    mock_engine = MagicMock()
    mock_adapter = MagicMock()
    mock_bus = MagicMock()
    mock_queue = MagicMock()

    url = Url("https://www.youtube.com/watch?v=123")
    fmt = FormatOption(
        format_id="137",
        extension="mp4",
        resolution="1080p",
        width=1920,
        height=1080,
        fps=30,
        filesize_bytes=5000000,
        stream_type=StreamType.VIDEO_AUDIO,
        download_type=DownloadType.VIDEO,
    )
    media = MediaMetadata(
        media_id=MediaId("yt_123"),
        url=url,
        title="Test Batch Video",
        platform="YouTube",
        formats=[fmt],
    )

    vm = MainViewModel(
        platform_adapter=mock_adapter,
        download_engine=mock_engine,
        repository=mock_repo,
        event_bus=mock_bus,
        download_queue=mock_queue,
    )

    batch_finished = []
    vm.batch_completed.connect(lambda s, f: batch_finished.append((s, f)))
    vm.analyze_uc.execute = MagicMock(return_value=media)

    with patch("threading.Thread") as mock_thread:
        mock_thread.side_effect = lambda target, daemon: MagicMock(start=target)
        vm.process_batch_downloads(["https://www.youtube.com/watch?v=123"], "Mejor calidad disponible", str(tmp_path))

    assert len(batch_finished) == 1
    assert batch_finished[0] == (1, 0)
    mock_queue.enqueue.assert_called_once()
