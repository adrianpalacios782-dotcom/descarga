import pytest

from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter


class _BareAdapter(BasePlatformAdapter):
    """Instancia mínima para probar el parseo de info de yt-dlp sin red."""

    def detect(self, url: Url) -> bool:
        return True

    def analyze(self, url: Url):  # pragma: no cover - no se usa en estos tests
        raise NotImplementedError


class TestParseYtdlpInfoMetadata:

    def _parse(self, info: dict) -> "object":
        adapter = _BareAdapter()
        url = Url("https://www.youtube.com/watch?v=abc12345678")
        return adapter._parse_ytdlp_info(url, info, "YouTube")

    def test_description_and_preview_fields_extracted(self) -> None:
        metadata = self._parse({
            "title": "Video Completo",
            "uploader": "Canal Uno",
            "description": "Sinopsis larga del contenido multimedia.",
            "duration": 512.0,
            "thumbnail": "https://i.ytimg.com/vi/abc/maxresdefault.jpg",
            "upload_date": "20240815",
            "formats": [],
            "url": "https://cdn.example/video.mp4",
            "ext": "mp4",
        })
        assert metadata.title == "Video Completo"
        assert metadata.author == "Canal Uno"
        assert metadata.description == "Sinopsis larga del contenido multimedia."
        assert metadata.thumbnail_url.endswith("maxresdefault.jpg")
        assert metadata.upload_date == "20240815"

    def test_missing_optional_fields_default_to_empty(self) -> None:
        metadata = self._parse({
            "title": "Solo Titulo",
            "formats": [],
            "url": "https://cdn.example/v.mp4",
        })
        assert metadata.description == ""
        assert metadata.thumbnail_url == ""
        assert metadata.upload_date == ""
        assert metadata.author == ""

    def test_channel_fallback_used_when_no_uploader(self) -> None:
        metadata = self._parse({
            "title": "T",
            "channel": "Canal Fallback",
            "formats": [],
            "url": "https://cdn.example/v.mp4",
        })
        assert metadata.author == "Canal Fallback"
