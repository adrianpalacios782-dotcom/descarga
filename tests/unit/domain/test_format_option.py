import pytest
from src.domain.entities.format_option import FormatOption, StreamType


class TestFormatOptionEntity:

    def test_create_valid_format_option(self) -> None:
        fmt = FormatOption(
            format_id="1080p_mp4",
            extension="mp4",
            resolution="1080p",
            width=1920,
            height=1080,
            fps=60.0,
            filesize_bytes=150 * 1024 * 1024
        )
        assert fmt.format_id == "1080p_mp4"
        assert fmt.extension == "mp4"
        assert fmt.get_human_filesize() == "~150.0 MB"

    def test_audio_only_format(self) -> None:
        fmt = FormatOption(
            format_id="best_audio",
            extension="mp3",
            stream_type=StreamType.AUDIO_ONLY,
            is_audio_only=True,
            bitrate_kbps=320.0,
            filesize_bytes=10 * 1024 * 1024
        )
        assert fmt.is_audio_only is True
        assert "Solo Audio" in fmt.get_description()
        assert "320 kbps" in fmt.get_description()

    def test_invalid_creation(self) -> None:
        with pytest.raises(ValueError):
            FormatOption(format_id="", extension="mp4")
        with pytest.raises(ValueError):
            FormatOption(format_id="1080p", extension="")
