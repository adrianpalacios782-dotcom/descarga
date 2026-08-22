"""Tests de seguridad del sistema de actualización.

Casos cubiertos:
5.  URL no permitida → rechazar
6.  HTTPS obligatorio
7.  SHA-256 correcto → permitir continuar
8.  SHA-256 incorrecto → bloquear ejecución
9.  descarga incompleta → bloquear ejecución
12. cancelación del usuario → no actualizar
13. archivo temporal eliminado correctamente
14. error del instalador → aplicación actual continúa funcionando

Extras anti-regresión: path traversal local, guardia de redirecciones,
parseo de checksums y campo digest.
"""
import hashlib
import threading
from pathlib import Path

import pytest

from src.domain.exceptions.domain_exceptions import (
    InvalidUpdateInfoError,
    UpdateError,
    UpdateDownloadError,
)
from src.domain.ports.update_source import RemoteAsset
from src.infrastructure.updater import http_client, update_config
from src.infrastructure.updater.github_releases_source import (
    GitHubReleasesSource,
    _digest_from_entry,
    _extract_sha256_for,
)
from src.infrastructure.updater.installer_downloader import InstallerDownloader
from src.infrastructure.updater.installer_launcher import (
    InstallerLauncher,
    cleanup_temp_dir,
    make_update_tempdir,
)

OFFICIAL_ASSET_URL = (
    "https://github.com/adrianpalacios782-dotcom/descarga/releases/"
    "download/v1.1.0/osvaldoDownloaderPro-1.1.0-Setup.exe"
)


def _payload(seed: bytes = b"MZ-fake-installer-body") -> bytes:
    return seed * 64


def _asset(
    payload: bytes,
    sha256: str | None = None,
    size: int | None = None,
    url: str = OFFICIAL_ASSET_URL,
) -> RemoteAsset:
    return RemoteAsset(
        name="osvaldoDownloaderPro-1.1.0-Setup.exe",
        url=url,
        size_bytes=len(payload) if size is None else size,
        sha256=hashlib.sha256(payload).hexdigest() if sha256 is None else sha256,
    )


class FakeResponse:
    """Respuesta HTTP mínima compatible con el contrato usado por el downloader."""

    def __init__(self, chunks: list[bytes], headers: dict | None = None) -> None:
        self._chunks = list(chunks)
        self._index = 0
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        if self._index >= len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


# ============================================================
# 6 + 5: POLÍTICA DE URLs (HTTPS y allowlist de hosts)
# ============================================================

class TestUrlPolicy:

    @pytest.mark.parametrize("url", [
        "http://api.github.com/repos/x/descarga/releases/latest",
        "ftp://api.github.com/x",
        "file:///etc/passwd",
        "https://evil.com/releases/latest",
        "https://api.github.com.evil.com/x",
        "https://github.com.evil.com/setup.exe",
        "https://127.0.0.1/setup.exe",
        "https://localhost/setup.exe",
        "",
        "not-a-url",
    ])
    def test_unsafe_urls_rejected(self, url):
        with pytest.raises(http_client.UnsafeUrlError):
            http_client.validate_url_or_raise(url, update_config.ALLOWED_METADATA_HOSTS)

    def test_https_mandatory_for_metadata(self):
        assert update_config.is_allowed_metadata_url(
            "https://api.github.com/repos/adrianpalacios782-dotcom/descarga/releases/latest"
        )
        assert not update_config.is_allowed_metadata_url(
            "http://api.github.com/repos/adrianpalacios782-dotcom/descarga/releases/latest"
        )

    def test_official_urls_accepted(self):
        assert update_config.is_allowed_asset_url(OFFICIAL_ASSET_URL)
        assert update_config.is_allowed_asset_url(
            "https://objects.githubusercontent.com/some/signed/path"
        )
        assert update_config.is_allowed_asset_url(
            "https://release-assets.githubusercontent.com/some/path"
        )

    def test_downloader_rejects_non_official_asset_url(self):
        downloader = InstallerDownloader(opener=lambda url: pytest.fail("no debe abrirse"))
        asset = RemoteAsset(
            name="x.exe", url="https://evil-cdn.example/setup.exe",
            size_bytes=10, sha256="a" * 64,
        )
        temp_dir = Path(make_update_tempdir())
        try:
            with pytest.raises(InvalidUpdateInfoError):
                downloader.download_to_tempdir(asset, temp_dir)
            assert list(temp_dir.iterdir()) == []
        finally:
            cleanup_temp_dir(temp_dir)


class TestRedirectGuard:

    def test_redirect_to_disallowed_host_blocked(self):
        handler = http_client._AllowlistRedirectHandler(update_config.ALLOWED_METADATA_HOSTS)
        request = http_client.Request("https://api.github.com/x")
        with pytest.raises(http_client.DisallowedRedirectError):
            handler.redirect_request(request, None, 302, "Found", {},
                                     "https://evil.com/steal")

    def test_redirect_to_allowed_host_permitted(self):
        import urllib.request as _ur

        handler = http_client._AllowlistRedirectHandler(update_config.ALLOWED_ASSET_HOSTS)
        request = _ur.Request("https://github.com/a/b/releases/download/v/setup.exe")
        result = handler.redirect_request(request, None, 302, "Found", {}, OFFICIAL_ASSET_URL)
        # Para hosts permitidos delega en el comportamiento estándar (nuevo Request).
        assert result is not None
        assert result.full_url == OFFICIAL_ASSET_URL


# ============================================================
# 7 / 8 / 9: VERIFICACIÓN DE DESCARGA (SHA-256, tamaño, integridad)
# ============================================================

class TestInstallerDownload:

    def test_sha256_correct_allows_continuation(self):
        payload = _payload()
        opener = lambda url: FakeResponse([payload], {"Content-Length": str(len(payload))})
        downloader = InstallerDownloader(opener=opener)
        temp_dir = Path(make_update_tempdir())
        try:
            final_path = downloader.download_to_tempdir(_asset(payload), temp_dir)
            assert final_path.is_file()
            assert not final_path.name.endswith(".part")
            assert final_path.read_bytes() == payload
        finally:
            cleanup_temp_dir(temp_dir)

    def test_chunked_download_reassembles_exactly(self):
        payload = _payload()
        chunks = [payload[i:i + 1024] for i in range(0, len(payload), 1024)]
        opener = lambda url: FakeResponse(chunks)
        downloader = InstallerDownloader(opener=opener)
        temp_dir = Path(make_update_tempdir())
        try:
            final_path = downloader.download_to_tempdir(_asset(payload), temp_dir)
            assert hashlib.sha256(final_path.read_bytes()).hexdigest() == hashlib.sha256(payload).hexdigest()
        finally:
            cleanup_temp_dir(temp_dir)

    def test_sha256_incorrect_blocks_execution(self):
        payload = _payload()
        tampered = payload[:-1] + bytes([payload[-1] ^ 0xFF])
        opener = lambda url: FakeResponse([tampered])
        downloader = InstallerDownloader(opener=opener)
        temp_dir = Path(make_update_tempdir())
        try:
            with pytest.raises(UpdateDownloadError, match="SHA-256"):
                downloader.download_to_tempdir(_asset(payload), temp_dir)
            # Nada ejecutable debe quedar: ni .part ni archivo final.
            assert list(temp_dir.iterdir()) == []
        finally:
            cleanup_temp_dir(temp_dir)

    def test_incomplete_download_blocks_execution(self):
        payload = _payload()
        truncated = payload[:len(payload) // 2]
        opener = lambda url: FakeResponse([truncated])  # menos bytes que los declarados
        downloader = InstallerDownloader(opener=opener)
        temp_dir = Path(make_update_tempdir())
        try:
            with pytest.raises(UpdateDownloadError, match="incompleta"):
                downloader.download_to_tempdir(_asset(payload), temp_dir)
            assert list(temp_dir.iterdir()) == []
        finally:
            cleanup_temp_dir(temp_dir)

    def test_download_larger_than_declared_aborts(self):
        payload = _payload()
        opener = lambda url: FakeResponse([payload])
        downloader = InstallerDownloader(opener=opener)
        temp_dir = Path(make_update_tempdir())
        try:
            with pytest.raises(UpdateDownloadError, match="tamaño"):
                downloader.download_to_tempdir(
                    _asset(payload, size=len(payload) - 100), temp_dir
                )
            assert list(temp_dir.iterdir()) == []
        finally:
            cleanup_temp_dir(temp_dir)

    def test_missing_checksum_refuses_to_download(self):
        downloader = InstallerDownloader(opener=lambda url: pytest.fail("no debe abrirse"))
        asset = RemoteAsset(name="setup.exe", url=OFFICIAL_ASSET_URL,
                            size_bytes=100, sha256=None)
        temp_dir = Path(make_update_tempdir())
        try:
            with pytest.raises(InvalidUpdateInfoError, match="checksum"):
                downloader.download_to_tempdir(asset, temp_dir)
        finally:
            cleanup_temp_dir(temp_dir)

    def test_progress_callback_reports(self):
        payload = _payload()
        seen = []
        opener = lambda url: FakeResponse([payload[:100], payload[100:]])
        downloader = InstallerDownloader(opener=opener)
        temp_dir = Path(make_update_tempdir())
        try:
            downloader.download_to_tempdir(
                _asset(payload), temp_dir,
                progress_callback=lambda d, t: seen.append((d, t)),
            )
            assert seen[-1][0] == len(payload)
        finally:
            cleanup_temp_dir(temp_dir)

    def test_user_cancellation_aborts_and_cleans(self):
        payload = _payload()
        cancel_event = threading.Event()
        cancel_event.set()

        class SlowResponse(FakeResponse):
            def read(self, size=-1):
                return b""  # la cancelación se detecta antes de leer

        opener = lambda url: SlowResponse([payload])
        downloader = InstallerDownloader(opener=opener)
        temp_dir = Path(make_update_tempdir())
        try:
            with pytest.raises(UpdateDownloadError, match="cancelada"):
                downloader.download_to_tempdir(
                    _asset(payload), temp_dir, cancel_event=cancel_event
                )
            assert list(temp_dir.iterdir()) == []
        finally:
            cleanup_temp_dir(temp_dir)

    def test_max_size_cap_enforced(self, monkeypatch):
        monkeypatch.setattr(update_config, "MAX_INSTALLER_BYTES", 8)
        payload = _payload()
        opener = lambda url: FakeResponse([payload])
        downloader = InstallerDownloader(opener=opener)
        temp_dir = Path(make_update_tempdir())
        try:
            with pytest.raises(UpdateDownloadError):
                downloader.download_to_tempdir(_asset(payload), temp_dir)
        finally:
            cleanup_temp_dir(temp_dir)


class TestLocalPathSafety:

    def test_traversal_collapses_to_safe_basename(self, tmp_path):
        # La ruta se NEUTRALIZA colapsando al componente final dentro de tempdir.
        resolved = InstallerDownloader._safe_local_path(tmp_path, "..\\..\\Windows\\evil.exe")
        assert resolved.parent == tmp_path.resolve()
        assert resolved.name == "evil.exe"

    def test_dotdot_only_rejected(self, tmp_path):
        for bad in ("..", ".", ""):
            with pytest.raises(UpdateDownloadError):
                InstallerDownloader._safe_local_path(tmp_path, bad)

    def test_absolute_name_collapses_inside_tempdir(self, tmp_path):
        resolved = InstallerDownloader._safe_local_path(tmp_path, "C:\\Windows\\system32\\cmd.exe")
        assert resolved.parent == tmp_path.resolve()

    def test_empty_or_dangerous_names_rejected(self, tmp_path):
        for bad in ('?file*', 'a:b'):
            with pytest.raises(UpdateDownloadError):
                InstallerDownloader._safe_local_path(tmp_path, bad)


# ============================================================
# 14: LANZADOR — verificación final y modo desarrollo
# ============================================================

class TestInstallerLauncher:

    def _verified_file(self, payload: bytes, sha256: str, size: int | None = None):
        temp_dir = Path(make_update_tempdir())
        target = temp_dir / update_config.LOCAL_INSTALLER_FILENAME
        target.write_bytes(payload)
        asset = RemoteAsset(
            name="osvaldoDownloaderPro-1.1.0-Setup.exe",
            url=OFFICIAL_ASSET_URL,
            size_bytes=size if size is not None else len(payload),
            sha256=sha256,
        )
        return temp_dir, target, asset

    def test_verify_ok_passes_preflight(self):
        payload = _payload()
        temp_dir, target, asset = self._verified_file(payload, hashlib.sha256(payload).hexdigest())
        launcher = InstallerLauncher(popen=lambda *a, **k: pytest.fail("no debe lanzarse aquí"))
        try:
            launcher.verify_installer_file(target, asset)  # no lanza
        finally:
            cleanup_temp_dir(temp_dir)

    def test_verify_wrong_hash_blocks_launch(self):
        payload = _payload()
        temp_dir, target, asset = self._verified_file(payload, "b" * 64)
        launcher = InstallerLauncher(popen=lambda *a, **k: pytest.fail("NO DEBE EJECUTARSE"))
        try:
            with pytest.raises(UpdateDownloadError, match="SHA-256"):
                launcher.verify_installer_file(target, asset)
        finally:
            cleanup_temp_dir(temp_dir)

    def test_verify_part_files_never_run(self):
        payload = _payload()
        temp_dir = Path(make_update_tempdir())
        part = temp_dir / (update_config.LOCAL_INSTALLER_FILENAME + ".part")
        part.write_bytes(payload)
        asset = RemoteAsset(name="s.exe", url=OFFICIAL_ASSET_URL,
                            size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        launcher = InstallerLauncher(popen=lambda *a, **k: pytest.fail("NO DEBE EJECUTARSE"))
        try:
            with pytest.raises(UpdateDownloadError, match="part"):
                launcher.verify_installer_file(part, asset)
        finally:
            cleanup_temp_dir(temp_dir)

    def test_dev_mode_never_executes_installer(self):
        from src.infrastructure.updater.installer_launcher import is_frozen_app

        if is_frozen_app():
            pytest.skip("Test diseñado para entorno no congelado")
        payload = _payload()
        temp_dir, target, asset = self._verified_file(payload, hashlib.sha256(payload).hexdigest())
        launcher = InstallerLauncher(popen=lambda *a, **k: pytest.fail("NO DEBE EJECUTARSE"))
        try:
            with pytest.raises(UpdateError, match="versión instalada"):
                launcher.install_and_restart(target, asset)
        finally:
            cleanup_temp_dir(temp_dir)

    def test_cleanup_removes_own_tempdirs(self):
        temp_dir = Path(make_update_tempdir())
        (temp_dir / "osvaldoDownloaderPro-Setup.exe").write_bytes(b"x")
        cleanup_temp_dir(temp_dir)
        assert not temp_dir.exists()

    def test_cleanup_ignores_dirs_outside_pattern(self, tmp_path_factory):
        foreign = tmp_path_factory.mktemp("proyecto-importante")
        cleanup_temp_dir(foreign)
        assert foreign.exists()

    def test_cleanup_ignores_nonexistent_paths(self):
        cleanup_temp_dir(Path(update_config.TEMP_DIR_PREFIX + "no-existe"))


# ============================================================
# FUENTE GITHUB: parseo de checksums y validación de assets
# ============================================================

class TestChecksumParsing:

    def test_extract_from_sha256sums_format(self):
        content = (
            "# SHA256SUMS\n"
            f"{'a' * 64}  osvaldoDownloaderPro-1.1.0-Setup.exe\n"
            f"{'c' * 64}  otro-archivo.zip\n"
        )
        assert _extract_sha256_for(content, "osvaldoDownloaderPro-1.1.0-Setup.exe") == "a" * 64

    def test_extract_handles_binary_marker_and_case(self):
        content = f"{'A' * 64} *OSVALDODOWNLOADERPRO-1.1.0-SETUP.EXE\n"
        assert _extract_sha256_for(content, "osvaldoDownloaderPro-1.1.0-Setup.exe") == "a" * 64

    def test_extract_resists_path_traversal_entries(self):
        content = f"{'d' * 64}  ../../../../Windows/system32/cmd.exe\n"
        assert _extract_sha256_for(content, "cmd.exe") is None

    def test_digest_field_valid(self):
        assert _digest_from_entry({"digest": "sha256:" + "a" * 64}) == "a" * 64

    @pytest.mark.parametrize("ignored", [
        "md5:" + "a" * 32,          # algoritmo no soportado → se ignora
        "sin-formato",              # sin separador algoritmo:valor
        None,
    ])
    def test_digest_field_ignores_unusable_values(self, ignored):
        entry = {} if ignored is None else {"digest": ignored}
        assert _digest_from_entry(entry) is None

    @pytest.mark.parametrize("malformed", [
        "sha256:corto",
        "sha256:" + "g" * 64,
        "sha256:",
    ])
    def test_digest_field_rejects_malformed_sha256(self, malformed):
        with pytest.raises(InvalidUpdateInfoError):
            _digest_from_entry({"digest": malformed})


class TestGitHubSourceValidation:

    @staticmethod
    def _release_json(asset_url: str, **extra):
        data = {
            "tag_name": "v1.1.0",
            "body": "Novedades",
            "assets": [
                {
                    "name": "osvaldoDownloaderPro-1.1.0-Setup.exe",
                    "browser_download_url": asset_url,
                    "size": 1234,
                },
                {
                    "name": "SHA256SUMS.txt",
                    "browser_download_url": (
                        "https://github.com/adrianpalacios782-dotcom/descarga/"
                        "releases/download/v1.1.0/SHA256SUMS.txt"
                    ),
                    "size": 200,
                },
            ],
        }
        data.update(extra)
        return data

    def test_asset_url_outside_allowlist_rejects_release(self):
        source = GitHubReleasesSource(
            fetch_json=lambda url: self._release_json("https://evil.example/setup.exe"),
            fetch_text=lambda url: "",
        )
        with pytest.raises(InvalidUpdateInfoError):
            source.get_latest_release()

    def test_checksum_asset_url_outside_allowlist_rejects_release(self):
        data = self._release_json(OFFICIAL_ASSET_URL)
        data["assets"][1]["browser_download_url"] = "http://api.github.com/steal"
        source = GitHubReleasesSource(
            fetch_json=lambda url: data,
            fetch_text=lambda url: "",
        )
        with pytest.raises(InvalidUpdateInfoError):
            source.get_latest_release()

    def test_release_without_installer_returns_no_asset(self):
        data = {
            "tag_name": "v1.1.0",
            "body": "",
            "assets": [{"name": "source.zip", "browser_download_url": OFFICIAL_ASSET_URL}],
        }
        source = GitHubReleasesSource(
            fetch_json=lambda url: data, fetch_text=lambda url: ""
        )
        release = source.get_latest_release()
        assert release.installer_asset is None
        assert release.tag_name == "v1.1.0"

    def test_checksum_file_content_used_for_hash(self):
        expected = "e" * 64
        sums = f"{expected}  osvaldoDownloaderPro-1.1.0-Setup.exe\n"

        def fake_json(url):
            assert url.startswith("https://api.github.com/")
            return self._release_json(OFFICIAL_ASSET_URL)

        def fake_text(url):
            assert update_config.is_allowed_asset_url(url)
            return sums

        source = GitHubReleasesSource(fetch_json=fake_json, fetch_text=fake_text)
        asset = source.get_latest_release().installer_asset
        assert asset.sha256 == expected
        assert asset.size_bytes == 1234

    def test_conflicting_hashes_rejected(self):
        data = self._release_json(OFFICIAL_ASSET_URL)
        data["assets"][0]["digest"] = "sha256:" + "f" * 64
        sums = f"{'e' * 64}  osvaldoDownloaderPro-1.1.0-Setup.exe\n"
        source = GitHubReleasesSource(
            fetch_json=lambda url: data, fetch_text=lambda url: sums
        )
        with pytest.raises(InvalidUpdateInfoError, match="discrepan"):
            source.get_latest_release()

    def test_network_error_translated_to_update_error(self):
        def boom(url):
            raise TimeoutError("timeout")

        source = GitHubReleasesSource(fetch_json=boom)
        with pytest.raises(UpdateError):
            source.get_latest_release()
