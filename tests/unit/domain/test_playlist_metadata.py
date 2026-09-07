from src.domain.entities.playlist_metadata import PlaylistEntry, PlaylistMetadata
from src.domain.value_objects.url import Url, is_playlist


def test_playlist_entry_creation():
    entry = PlaylistEntry(
        video_id="vid1",
        title="Video 1",
        url="https://www.youtube.com/watch?v=vid1",
        duration_seconds=180.0,
        uploader="Channel A",
        thumbnail_url="https://img.com/1.jpg",
    )
    assert entry.id == "vid1"
    assert entry.video_id == "vid1"
    assert entry.title == "Video 1"
    assert entry.duration_seconds == 180.0


def test_playlist_metadata_creation():
    entries = [
        PlaylistEntry(video_id=f"v{i}", title=f"Track {i}", url=f"https://yt.com/watch?v=v{i}", duration_seconds=120.0)
        for i in range(5)
    ]
    playlist = PlaylistMetadata(
        playlist_id="pl_123",
        title="Best Hits Album",
        url=Url("https://www.youtube.com/playlist?list=pl_123"),
        platform="YouTube",
        entries=entries,
        uploader="Great Artist",
    )
    assert playlist.id == "pl_123"
    assert playlist.title == "Best Hits Album"
    assert playlist.item_count == 5
    assert playlist.total_duration_seconds == 600.0


def test_url_is_playlist():
    assert is_playlist("https://www.youtube.com/playlist?list=PL12345") is True
    assert is_playlist("https://www.youtube.com/watch?v=123&list=PL12345") is True
    assert is_playlist("https://www.youtube.com/watch?v=123") is False
    assert is_playlist("https://twitch.tv/streamer") is False
