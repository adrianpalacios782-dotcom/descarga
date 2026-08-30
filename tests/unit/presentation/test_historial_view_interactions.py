from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption, StreamType, DownloadType
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.presentation.views.historial_view import HistorialView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_task(tmp_path):
    video_file = tmp_path / "video.mp4"
    video_file.write_text("dummy")

    url = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    media = MediaMetadata(
        media_id=MediaId("yt_dQw4w9WgXcQ"),
        url=url,
        title="Never Gonna Give You Up",
        author="Rick Astley",
        duration_seconds=212.0,
        platform="YouTube",
    )
    fmt = FormatOption(
        format_id="137",
        extension="mp4",
        resolution="1080p",
        width=1920,
        height=1080,
        fps=30,
        filesize_bytes=50000000,
        stream_type=StreamType.VIDEO_AUDIO,
        download_type=DownloadType.VIDEO,
    )
    return DownloadTask(
        id=DownloadId("task-12345"),
        media=media,
        selected_format=fmt,
        destination_path=str(video_file),
        status=DownloadState.COMPLETED,
        total_bytes=50000000,
    )


def test_historial_view_load_and_filter(qapp, sample_task):
    view = HistorialView()
    view.load_history([sample_task])

    assert view.table.rowCount() == 1
    assert view.table.item(0, 0).text() == "Never Gonna Give You Up"
    assert view.table.item(0, 1).text() == "YouTube"

    # Filtro que no coincide
    view.search_input.setText("Inexistente")
    assert view.table.rowCount() == 0

    # Filtro que sí coincide
    view.search_input.setText("Rick")
    assert view.table.rowCount() == 1


def test_historial_view_double_click_existing_file(qapp, sample_task):
    view = HistorialView()
    view.load_history([sample_task])

    received_path = []
    view.open_file_requested.connect(lambda p: received_path.append(p))

    item = view.table.item(0, 0)
    assert item is not None
    view._on_item_double_clicked(item)

    assert len(received_path) == 1
    assert received_path[0] == sample_task.destination_path


def test_historial_view_delete_confirmation(qapp, sample_task):
    view = HistorialView()
    view.load_history([sample_task])

    received_id = []
    view.delete_task_requested.connect(lambda t_id: received_id.append(t_id))

    # Simular respuesta afirmativa en QMessageBox
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        view._confirm_and_delete(sample_task)

    assert len(received_id) == 1
    assert received_id[0] == sample_task.id.value


def test_historial_view_copy_url(qapp, sample_task):
    view = HistorialView()
    view.load_history([sample_task])

    view._copy_url_to_clipboard(sample_task.media.url.value)
    clipboard = QApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_main_view_model_delete_task():
    from src.presentation.view_models.main_view_model import MainViewModel
    from src.domain.value_objects.download_id import DownloadId

    mock_repo = MagicMock()
    mock_engine = MagicMock()
    mock_adapter = MagicMock()
    mock_bus = MagicMock()

    vm = MainViewModel(
        platform_adapter=mock_adapter,
        download_engine=mock_engine,
        repository=mock_repo,
        event_bus=mock_bus,
    )

    success = vm.delete_task("task-12345")
    assert success is True
    mock_repo.delete.assert_called_once_with(DownloadId("task-12345"))
