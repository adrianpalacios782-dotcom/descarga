import pytest
from PySide6.QtWidgets import QApplication
from src.domain.entities.playlist_metadata import PlaylistEntry, PlaylistMetadata
from src.domain.value_objects.url import Url
from src.presentation.components.playlist_download_dialog import PlaylistDownloadDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_playlist_download_dialog_init(qapp):
    entries = [
        PlaylistEntry(video_id="v1", title="Song 1", url="https://yt.com/watch?v=v1", duration_seconds=180.0),
        PlaylistEntry(video_id="v2", title="Song 2", url="https://yt.com/watch?v=v2", duration_seconds=210.0),
    ]
    playlist = PlaylistMetadata(
        playlist_id="pl1",
        title="Test Album",
        url=Url("https://youtube.com/playlist?list=pl1"),
        platform="YouTube",
        entries=entries,
        uploader="Artist X",
    )
    dlg = PlaylistDownloadDialog(playlist=playlist)
    assert dlg.table.rowCount() == 2
    assert len(dlg.get_selected_urls()) == 2

    # Deselect all
    dlg._deselect_all()
    assert len(dlg.get_selected_urls()) == 0
    assert dlg.btn_start.isEnabled() is False

    # Select all
    dlg._select_all()
    assert len(dlg.get_selected_urls()) == 2
    assert dlg.btn_start.isEnabled() is True
