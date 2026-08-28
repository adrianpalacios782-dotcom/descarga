"""Test de regresión para YtDlpDownloadEngine._canonicalize_final_path."""
import os
from src.domain.entities.download_task import DownloadTask
from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine


def test_canonicalize_final_path_with_different_extension_or_name(tmp_path):
    dest = str(tmp_path / "video.mp4")
    # Simular archivo descargado por yt-dlp con extensión o nombre ligeramente diferente (ej. .mkv)
    actual_download = str(tmp_path / "video.mkv")
    with open(actual_download, "wb") as f:
        f.write(b"dummy video content")

    url = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    media = MediaMetadata(
        media_id=MediaId.from_string(url.value),
        url=url,
        platform="YouTube",
        title="Test Video",
        duration_seconds=10.0,
    )
    fmt = FormatOption(format_id="137", extension="mp4")
    task = DownloadTask(
        id=DownloadId.generate(),
        media=media,
        selected_format=fmt,
        destination_path=dest,
    )

    engine = YtDlpDownloadEngine()
    # Esta llamada previamente lanzaba: ValueError: not enough values to unpack (expected 3, got 2)
    canonical = engine._canonicalize_final_path(actual_download, task)

    assert os.path.exists(canonical)
    assert canonical.endswith(".mkv")
    assert task.destination_path == canonical
