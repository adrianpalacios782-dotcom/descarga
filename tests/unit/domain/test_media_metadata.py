import pytest
from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url


class TestMediaMetadataEntity:

    def test_media_metadata_creation_and_duration_formatting(self) -> None:
        url = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        media = MediaMetadata(
            media_id=MediaId.from_string(url.value),
            url=url,
            platform="YouTube",
            title="Video Demostración",
            author="Canal Pruebas",
            duration_seconds=3665.0
        )
        assert media.title == "Video Demostración"
        assert media.get_duration_formatted() == "01:01:05"

        media_short = MediaMetadata(
            media_id=MediaId.generate(),
            url=url,
            platform="YouTube",
            title="Short Video",
            duration_seconds=125.0
        )
        assert media_short.get_duration_formatted() == "02:05"

    def test_format_selection_helpers(self) -> None:
        url = Url("https://tiktok.com/@user/video/1")
        fmt1 = FormatOption(format_id="720p", extension="mp4", height=720, fps=30.0)
        fmt2 = FormatOption(format_id="1080p", extension="mp4", height=1080, fps=60.0)
        audio_fmt = FormatOption(format_id="audio", extension="mp3", is_audio_only=True, bitrate_kbps=320.0)

        media = MediaMetadata(
            media_id=MediaId.generate(),
            url=url,
            platform="TikTok",
            title="TikTok Video",
            formats=[fmt1, fmt2, audio_fmt]
        )

        assert media.get_format_by_id("1080p") == fmt2
        assert media.get_best_video_format() == fmt2
        assert media.get_best_audio_format() == audio_fmt

    def test_empty_title_raises_value_error(self) -> None:
        url = Url("https://instagram.com/p/123")
        with pytest.raises(ValueError):
            MediaMetadata(
                media_id=MediaId.generate(),
                url=url,
                platform="Instagram",
                title="  "
            )
