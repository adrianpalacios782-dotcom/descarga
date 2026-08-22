import socket

import pytest

from src.infrastructure.adapters.media import thumbnail_fetcher
from src.infrastructure.adapters.media.thumbnail_fetcher import (
    InsecureThumbnailUrlError,
    MAX_THUMBNAIL_BYTES,
    ThumbnailFetchError,
    _ValidatingRedirectHandler,
    fetch_thumbnail,
    validate_thumbnail_url,
)


PUBLIC_DNS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
PRIVATE_DNS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))]


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(
        thumbnail_fetcher.socket, "getaddrinfo", lambda host, port, proto=0: list(PUBLIC_DNS)
    )


class TestValidateThumbnailUrl:

    def test_accepts_https_public_domain(self) -> None:
        url = "https://i.ytimg.com/vi/abc/maxresdefault.jpg"
        assert validate_thumbnail_url(url) == url

    @pytest.mark.parametrize("url", [
        "http://i.ytimg.com/vi/abc.jpg",
        "ftp://i.ytimg.com/vi/abc.jpg",
        "file:///etc/passwd",
    ])
    def test_rejects_non_https_schemes(self, url) -> None:
        with pytest.raises(InsecureThumbnailUrlError):
            validate_thumbnail_url(url)

    def test_rejects_missing_hostname(self) -> None:
        with pytest.raises(InsecureThumbnailUrlError):
            validate_thumbnail_url("https:///ruta.jpg")

    @pytest.mark.parametrize("url", [
        "https://localhost/img.jpg",
        "https://127.0.0.1/img.jpg",
        "https://10.1.2.3/img.jpg",
        "https://192.168.1.50/img.jpg",
        "https://169.254.1.9/img.jpg",
    ])
    def test_rejects_localhost_and_private_literals(self, url) -> None:
        with pytest.raises(InsecureThumbnailUrlError):
            validate_thumbnail_url(url)

    def test_rejects_non_standard_port(self) -> None:
        with pytest.raises(InsecureThumbnailUrlError):
            validate_thumbnail_url("https://i.ytimg.com:8443/img.jpg")

    def test_rejects_unresolvable_host(self, monkeypatch) -> None:
        monkeypatch.setattr(
            thumbnail_fetcher.socket, "getaddrinfo", lambda host, port, proto=0: []
        )
        with pytest.raises(InsecureThumbnailUrlError):
            validate_thumbnail_url("https://no-resuelve.invalid/img.jpg")

    def test_rejects_dns_resolving_to_private_address(self, monkeypatch) -> None:
        monkeypatch.setattr(
            thumbnail_fetcher.socket, "getaddrinfo", lambda host, port, proto=0: list(PRIVATE_DNS)
        )
        with pytest.raises(InsecureThumbnailUrlError):
            validate_thumbnail_url("https://i.ytimg.com/vi/abc.jpg")

    def test_empty_url(self) -> None:
        with pytest.raises(InsecureThumbnailUrlError):
            validate_thumbnail_url("")


class TestRedirectHandler:

    def test_rejects_insecure_redirect_target(self) -> None:
        handler = _ValidatingRedirectHandler()
        with pytest.raises(InsecureThumbnailUrlError):
            handler.redirect_request(None, None, 301, "moved", {}, "http://evil.example/img.jpg")

    def test_blocks_after_max_redirects(self) -> None:
        handler = _ValidatingRedirectHandler()
        handler.redirects_left = 0
        with pytest.raises(ThumbnailFetchError):
            handler.redirect_request(None, None, 301, "moved", {}, "https://ok.example/img.jpg")


class FakeResponse:
    def __init__(self, headers=None, body=b"x" * 32, status=200) -> None:
        self.status = status
        self.headers = headers if headers is not None else {
            "Content-Type": "image/jpeg",
            "Content-Length": str(len(body)),
        }
        self._body = body
        self._consumed = False

    def read(self, size=-1) -> bytes:
        if self._consumed:
            return b""
        self._consumed = True
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, response) -> None:
        self.response = response
        self.last_request = None
        self.last_timeout = None

    def open(self, request, timeout=None):
        self.last_request = request
        self.last_timeout = timeout
        return self.response


class TestFetchThumbnail:

    def _patch_opener(self, monkeypatch, response) -> FakeOpener:
        opener = FakeOpener(response)
        monkeypatch.setattr(thumbnail_fetcher.urllib.request, "build_opener", lambda handler=None: opener)
        return opener

    def test_successful_download_returns_bytes(self, monkeypatch) -> None:
        body = b"\xff\xd8\xff\xe0fakejpeg"
        response = FakeResponse(body=body)
        self._patch_opener(monkeypatch, response)

        data = fetch_thumbnail("https://i.ytimg.com/vi/abc/maxresdefault.jpg")
        assert data == body

    def test_rejects_non_image_content_type(self, monkeypatch) -> None:
        response = FakeResponse(headers={"Content-Type": "text/html"})
        self._patch_opener(monkeypatch, response)

        with pytest.raises(ThumbnailFetchError, match="no es una imagen"):
            fetch_thumbnail("https://i.ytimg.com/vi/abc/maxresdefault.jpg")

    def test_rejects_oversized_declared_length(self, monkeypatch) -> None:
        response = FakeResponse(headers={
            "Content-Type": "image/jpeg",
            "Content-Length": str(MAX_THUMBNAIL_BYTES + 1),
        })
        self._patch_opener(monkeypatch, response)

        with pytest.raises(ThumbnailFetchError, match="tamaño máximo"):
            fetch_thumbnail("https://i.ytimg.com/vi/abc.jpg")

    def test_rejects_body_larger_than_cap(self, monkeypatch) -> None:
        body = b"A" * (MAX_THUMBNAIL_BYTES + 1024)
        response = FakeResponse(body=body)
        self._patch_opener(monkeypatch, response)

        with pytest.raises(ThumbnailFetchError, match="tamaño máximo"):
            fetch_thumbnail("https://i.ytimg.com/vi/abc.jpg")

    def test_network_error_wrapped(self, monkeypatch) -> None:
        class BrokenOpener:
            def open(self, request, timeout=None):
                raise thumbnail_fetcher.urllib.error.URLError("conexión rechazada")

        monkeypatch.setattr(
            thumbnail_fetcher.urllib.request, "build_opener", lambda handler=None: BrokenOpener()
        )

        with pytest.raises(ThumbnailFetchError, match="Fallo de red"):
            fetch_thumbnail("https://i.ytimg.com/vi/abc.jpg")
