import pytest
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.entities.subtitle import SubtitleConfig, SubtitleMode, SubtitleTrack
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url


def test_subtitle_track_validation():
    track = SubtitleTrack(
        language_code="es",
        name="Español",
        extension="vtt",
        is_auto_generated=False,
    )
    assert track.language_code == "es"
    assert track.name == "Español"
    assert track.extension == "vtt"
    assert track.is_auto_generated is False

    with pytest.raises(ValueError, match="language_code"):
        SubtitleTrack(language_code="")


def test_subtitle_config_defaults():
    cfg = SubtitleConfig()
    assert cfg.mode == SubtitleMode.NONE
    assert cfg.language_code is None
    assert cfg.is_auto_generated is False


def test_subtitle_config_custom():
    cfg = SubtitleConfig(
        mode=SubtitleMode.EMBED,
        language_code="en",
        is_auto_generated=True,
    )
    assert cfg.mode == SubtitleMode.EMBED
    assert cfg.language_code == "en"
    assert cfg.is_auto_generated is True


def test_media_metadata_subtitles():
    url = Url("https://www.youtube.com/watch?v=123")
    track = SubtitleTrack(language_code="en", name="English")
    meta = MediaMetadata(
        media_id=MediaId("yt_123"),
        url=url,
        platform="YouTube",
        title="Test Subtitles",
        subtitles=[track],
    )
    assert len(meta.subtitles) == 1
    assert meta.subtitles[0].language_code == "en"
