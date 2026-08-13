import pytest
from src.domain.exceptions.domain_exceptions import InvalidUrlError
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url


class TestUrlValueObject:

    def test_valid_http_and_https_url(self) -> None:
        url1 = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert url1.value == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert str(url1) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        url2 = Url("http://tiktok.com/@user/video/123456")
        assert url2.value == "http://tiktok.com/@user/video/123456"

    def test_invalid_url_protocol(self) -> None:
        with pytest.raises(InvalidUrlError, match="Protocolo 'ftp' no soportado"):
            Url("ftp://files.example.com/video.mp4")

    def test_empty_or_whitespace_url(self) -> None:
        with pytest.raises(InvalidUrlError):
            Url("")
        with pytest.raises(InvalidUrlError):
            Url("   ")

    def test_ssrf_and_localhost_prevention(self) -> None:
        with pytest.raises(InvalidUrlError, match="No se permiten URLs dirigidas a localhost"):
            Url("http://localhost:8080/secret")

        with pytest.raises(InvalidUrlError, match="No se permiten URLs dirigidas a localhost"):
            Url("http://127.0.0.1/admin")

    @pytest.mark.parametrize(
        "url_str, expected_platform",
        [
            ("https://www.youtube.com/watch?v=123", "YouTube"),
            ("https://youtu.be/123", "YouTube"),
            ("https://www.tiktok.com/@user/video/999", "TikTok"),
            ("https://www.instagram.com/reel/C123/", "Instagram"),
            ("https://www.facebook.com/watch/?v=456", "Facebook"),
            ("https://fb.watch/xyz/", "Facebook"),
            ("https://vimeo.com/78910", "Generic"),
        ],
    )
    def test_platform_detection(self, url_str: str, expected_platform: str) -> None:
        url = Url(url_str)
        assert url.detect_platform() == expected_platform


class TestDownloadIdValueObject:

    def test_generate_and_string_representation(self) -> None:
        download_id = DownloadId.generate()
        assert isinstance(download_id.value, str)
        assert len(download_id.value) > 10
        assert str(download_id) == download_id.value

    def test_empty_download_id_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            DownloadId("")


class TestMediaIdValueObject:

    def test_generate_media_id(self) -> None:
        media_id = MediaId.generate()
        assert isinstance(media_id.value, str)
        assert len(media_id.value) > 0

    def test_from_string_deterministic(self) -> None:
        m1 = MediaId.from_string("https://youtube.com/watch?v=123")
        m2 = MediaId.from_string("https://youtube.com/watch?v=123")
        assert m1 == m2
        assert m1.value.startswith("media_")
