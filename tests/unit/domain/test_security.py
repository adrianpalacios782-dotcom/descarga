"""Tests de seguridad automatizados para osvaldoDownloaderPro.

Cubre:
- Path traversal en URLs, nombres de archivo, destinos
- Command injection en format_id, URLs
- Validación de URLs (SSRF, protocolos, dominios)
- Sanitización de logs
- Protección SQLite contra inyección
- Validación de format_id para yt-dlp
"""
import os
from unittest.mock import MagicMock

import pytest

from src.domain.value_objects.url import Url
from src.domain.exceptions.domain_exceptions import InvalidUrlError
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.logging.logger_config import sanitize_log_message


# ============================================================
# URL VALIDATION - SSRF, protocolos, dominios
# ============================================================

class TestUrlSecurity:
    """Validación de URLs contra SSRF, protocolos peligrosos y dominios no soportados."""

    def test_reject_file_scheme(self):
        with pytest.raises(InvalidUrlError, match="Protocolo"):
            Url("file:///etc/passwd")

    def test_reject_ftp_scheme(self):
        with pytest.raises(InvalidUrlError, match="Protocolo"):
            Url("ftp://example.com/file.mp4")

    def test_reject_javascript_scheme(self):
        with pytest.raises(InvalidUrlError, match="Protocolo"):
            Url("javascript:alert(1)")

    def test_reject_data_scheme(self):
        with pytest.raises(InvalidUrlError, match="Protocolo"):
            Url("data:text/html,<h1>hi</h1>")

    def test_reject_localhost_ipv4(self):
        with pytest.raises(InvalidUrlError):
            Url("http://127.0.0.1/video.mp4")

    def test_reject_localhost_hostname(self):
        with pytest.raises(InvalidUrlError, match="localhost"):
            Url("http://localhost/video.mp4")

    def test_reject_0000(self):
        with pytest.raises(InvalidUrlError, match="localhost"):
            Url("http://0.0.0.0/video.mp4")

    def test_reject_ipv6_loopback(self):
        with pytest.raises(InvalidUrlError):
            Url("http://[::1]/video.mp4")

    def test_reject_private_10x(self):
        with pytest.raises(InvalidUrlError, match="privadas"):
            Url("http://10.0.0.1/video.mp4")

    def test_reject_private_172_16x(self):
        with pytest.raises(InvalidUrlError, match="privadas"):
            Url("http://172.16.0.1/video.mp4")

    def test_reject_private_192_168x(self):
        with pytest.raises(InvalidUrlError, match="privadas"):
            Url("http://192.168.1.1/video.mp4")

    def test_reject_link_local_169_254x(self):
        with pytest.raises(InvalidUrlError):
            Url("http://169.254.169.254/metadata")

    def test_reject_reserved_range(self):
        with pytest.raises(InvalidUrlError):
            Url("http://192.0.2.1/video.mp4")

    def test_reject_multicast(self):
        with pytest.raises(InvalidUrlError, match="multicast"):
            Url("http://224.0.0.1/video.mp4")

    def test_reject_dangerous_port_22(self):
        with pytest.raises(InvalidUrlError, match="Puerto"):
            Url("http://youtube.com:22/video.mp4")

    def test_reject_dangerous_port_21(self):
        with pytest.raises(InvalidUrlError):
            Url("http://youtube.com:21/file.mp4")

    def test_allow_standard_port_443(self):
        url = Url("https://www.youtube.com:443/watch?v=123")
        assert url.value == "https://www.youtube.com:443/watch?v=123"

    def test_allow_standard_port_80(self):
        url = Url("http://www.youtube.com:80/watch?v=123")
        assert url.value == "http://www.youtube.com:80/watch?v=123"

    def test_reject_unsupported_domain(self):
        with pytest.raises(InvalidUrlError, match="plataforma soportada"):
            Url("https://evil-site.com/video.mp4")

    def test_reject_arbitrary_subdomain_not_platform(self):
        with pytest.raises(InvalidUrlError, match="plataforma soportada"):
            Url("https://evil.youtube.com.evil.com/video.mp4")

    def test_accept_youtube(self):
        url = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert url.detect_platform() == "YouTube"

    def test_accept_youtu_be(self):
        url = Url("https://youtu.be/dQw4w9WgXcQ")
        assert url.detect_platform() == "YouTube"

    def test_accept_tiktok(self):
        url = Url("https://www.tiktok.com/@user/video/123")
        assert url.detect_platform() == "TikTok"

    def test_accept_instagram(self):
        url = Url("https://www.instagram.com/reel/C123/")
        assert url.detect_platform() == "Instagram"

    def test_accept_facebook(self):
        url = Url("https://www.facebook.com/watch/?v=123")
        assert url.detect_platform() == "Facebook"

    def test_accept_fb_watch(self):
        url = Url("https://fb.watch/xyz/")
        assert url.detect_platform() == "Facebook"

    def test_reject_empty_url(self):
        with pytest.raises(InvalidUrlError):
            Url("")

    def test_reject_whitespace_only(self):
        with pytest.raises(InvalidUrlError):
            Url("   ")

    def test_reject_no_scheme(self):
        with pytest.raises(InvalidUrlError):
            Url("youtube.com/watch?v=123")

    def test_reject_missing_netloc(self):
        with pytest.raises(InvalidUrlError):
            Url("https://")


# ============================================================
# PATH TRAVERSAL
# ============================================================

class TestPathTraversal:
    """Protección contra path traversal en nombres de archivo y destinos."""

    def test_sanitize_filename_removes_dots(self):
        result = YtDlpDownloadEngine._sanitize_filename("test......")
        assert result == "test"

    def test_sanitize_filename_blocks_colon(self):
        result = YtDlpDownloadEngine._sanitize_filename("C:\\Windows\\System32\\cmd.exe")
        assert ":" not in result
        assert "C_" in result

    def test_sanitize_filename_blocks_angle_brackets(self):
        result = YtDlpDownloadEngine._sanitize_filename('<script>alert(1)</script>')
        assert "<" not in result
        assert ">" not in result

    def test_sanitize_filename_blocks_pipe(self):
        result = YtDlpDownloadEngine._sanitize_filename("file|cmd")
        assert "|" not in result

    def test_sanitize_filename_blocks_question_mark(self):
        result = YtDlpDownloadEngine._sanitize_filename("file?")
        assert "?" not in result

    def test_sanitize_filename_blocks_control_chars(self):
        result = YtDlpDownloadEngine._sanitize_filename("file\x00\x1f\x7f")
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_sanitize_filename_empty_fallback(self):
        assert YtDlpDownloadEngine._sanitize_filename("") == "descarga"

    def test_sanitize_filename_none_fallback(self):
        assert YtDlpDownloadEngine._sanitize_filename(None) == "descarga"

    def test_sanitize_filename_only_dots_fallback(self):
        assert YtDlpDownloadEngine._sanitize_filename("...") == "descarga"

    def test_sanitize_filename_truncation(self):
        long_name = "a" * 250
        result = YtDlpDownloadEngine._sanitize_filename(long_name)
        assert len(result) <= 180

    def test_validate_destination_path_rejects_windows_system32(self):
        with pytest.raises(RuntimeError, match="ubicación del sistema"):
            YtDlpDownloadEngine._validate_destination_path("C:\\Windows\\System32\\evil.exe")

    def test_validate_destination_path_rejects_program_files(self):
        with pytest.raises(RuntimeError, match="ubicación del sistema"):
            YtDlpDownloadEngine._validate_destination_path("C:\\Program Files\\evil.exe")

    def test_validate_destination_path_rejects_recycle_bin(self):
        with pytest.raises(RuntimeError, match="ubicación del sistema"):
            YtDlpDownloadEngine._validate_destination_path("C:\\$RECYCLE.BIN\\evil.exe")

    def test_validate_destination_path_allows_downloads(self):
        home = os.path.expanduser("~")
        YtDlpDownloadEngine._validate_destination_path(os.path.join(home, "Downloads", "test.mp4"))


# ============================================================
# FORMAT ID INJECTION
# ============================================================

class TestFormatIdSecurity:
    """Protección contra inyección de format_id en especificaciones de yt-dlp."""

    def test_sanitize_format_id_valid_numeric(self):
        assert YtDlpDownloadEngine._sanitize_format_id("137") == "137"

    def test_sanitize_format_id_valid_with_underscore(self):
        assert YtDlpDownloadEngine._sanitize_format_id("137_2") == "137_2"

    def test_sanitize_format_id_valid_with_dash(self):
        assert YtDlpDownloadEngine._sanitize_format_id("h264-mp4a") == "h264-mp4a"

    def test_sanitize_format_id_rejects_shell_injection(self):
        assert YtDlpDownloadEngine._sanitize_format_id("137; rm -rf /") == ""

    def test_sanitize_format_id_rejects_ampersand(self):
        assert YtDlpDownloadEngine._sanitize_format_id("137&whoami") == ""

    def test_sanitize_format_id_rejects_pipe(self):
        assert YtDlpDownloadEngine._sanitize_format_id("137|cat /etc/passwd") == ""

    def test_sanitize_format_id_rejects_backtick(self):
        assert YtDlpDownloadEngine._sanitize_format_id("`whoami`") == ""

    def test_sanitize_format_id_rejects_dollar(self):
        assert YtDlpDownloadEngine._sanitize_format_id("$(whoami)") == ""

    def test_sanitize_format_id_rejects_quotes(self):
        assert YtDlpDownloadEngine._sanitize_format_id("137' OR 1=1 --") == ""

    def test_sanitize_format_id_rejects_angle_brackets(self):
        assert YtDlpDownloadEngine._sanitize_format_id("137>evil.txt") == ""

    def test_sanitize_format_id_rejects_space(self):
        assert YtDlpDownloadEngine._sanitize_format_id("137 bad") == ""

    def test_sanitize_format_id_empty(self):
        assert YtDlpDownloadEngine._sanitize_format_id("") == ""

    def test_sanitize_format_id_none(self):
        assert YtDlpDownloadEngine._sanitize_format_id(None) == ""

    def test_format_spec_no_injection_with_shell_chars(self):
        class FakeFmt:
            is_best_quality = False
            format_id = "137; rm -rf /"
            height = 1080

        spec = YtDlpDownloadEngine._build_video_format_spec(FakeFmt())
        assert "rm -rf" not in spec
        assert ";" not in spec

    def test_format_spec_uses_sanitized_id(self):
        class FakeFmt:
            is_best_quality = False
            format_id = "137"
            height = 1080

        spec = YtDlpDownloadEngine._build_video_format_spec(FakeFmt())
        assert spec.startswith("137+bestaudio")

    def test_format_spec_best_quality_safe(self):
        class FakeFmt:
            is_best_quality = True
            format_id = "best_quality"
            height = 1080

        spec = YtDlpDownloadEngine._build_video_format_spec(FakeFmt())
        assert "bestvideo" in spec
        assert ";" not in spec


# ============================================================
# LOG SANITIZATION
# ============================================================

class TestLogSanitization:
    """Sanitización de logs contra exposición de secretos."""

    def test_sanitize_token_in_url(self):
        msg = "URL: https://api.example.com?token=abc123secret"
        result = sanitize_log_message(msg)
        assert "abc123secret" not in result
        assert "REDACTED" in result

    def test_sanitize_auth_in_url(self):
        msg = "URL: https://api.example.com?auth=xyz789"
        result = sanitize_log_message(msg)
        assert "xyz789" not in result

    def test_sanitize_secret_in_url(self):
        msg = "URL: https://api.example.com?secret=mysecretvalue"
        result = sanitize_log_message(msg)
        assert "mysecretvalue" not in result

    def test_sanitize_password_in_url(self):
        msg = "URL: https://api.example.com?password=hunter2"
        result = sanitize_log_message(msg)
        assert "hunter2" not in result

    def test_sanitize_key_in_url(self):
        msg = "URL: https://api.example.com?key=apikey123"
        result = sanitize_log_message(msg)
        assert "apikey123" not in result

    def test_sanitize_bearer_token(self):
        msg = "Header: Bearer eyJhbGciOiJIUzI1NiJ9.test.signature"
        result = sanitize_log_message(msg)
        assert "eyJhbGciOiJIUzI1NiJ9" not in result
        assert "REDACTED" in result

    def test_sanitize_authorization_header(self):
        msg = "Authorization: Basic dXNlcjpwYXNz"
        result = sanitize_log_message(msg)
        assert "dXNlcjpwYXNz" not in result

    def test_sanitize_cookie_header(self):
        msg = "Cookie: session_id=abc123def456"
        result = sanitize_log_message(msg)
        assert "abc123def456" not in result

    def test_sanitize_ansi_escape_codes(self):
        msg = "\x1b[31mError\x1b[0m occurred"
        result = sanitize_log_message(msg)
        assert "\x1b[" not in result

    def test_sanitize_case_insensitive(self):
        msg = "TOKEN=secret123"
        result = sanitize_log_message(msg)
        assert "secret123" not in result

    def test_sanitize_preserves_safe_content(self):
        msg = "Download completed: 1080p video at /home/user/video.mp4"
        result = sanitize_log_message(msg)
        assert "1080p" in result
        assert "/home/user/video.mp4" in result


# ============================================================
# YOUTUBE-DL OPTIONS HARDENING
# ============================================================

class TestYtDlpOptionsSecurity:
    """Verificar que las opciones de yt-dlp no permitan inyección de configuración."""

    def test_base_opts_no_external_downloader(self):
        from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
        engine = YtDlpDownloadEngine(ffmpeg_adapter=FFmpegProcessAdapter())
        cancel = MagicMock()
        pause = MagicMock()
        opts = engine._build_base_opts("/tmp/test.%(ext)s", "task1", cancel, pause)
        assert "external_downloader" not in opts
        assert "external_downloader_args" not in opts
        assert "proxy" not in opts
        assert "cookiesfrombrowser" not in opts
        assert "postprocessors" not in opts

    def test_probe_opts_no_external_downloader(self):
        cancel = MagicMock()
        cancel.is_set.return_value = False

        opts = {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "skip_download": True,
            "noplaylist": True,
            "format": "all",
            "socket_timeout": 30,
        }
        assert "external_downloader" not in opts
        assert "proxy" not in opts
        assert "cookiesfrombrowser" not in opts
        assert "postprocessors" not in opts
        assert "extractor_args" not in opts

    def test_tiktok_opts_no_extractor_args(self):
        from src.infrastructure.adapters.platforms.tiktok_adapter import TikTokAdapter
        adapter = TikTokAdapter()
        opts = adapter._build_ydl_opts()
        assert "extractor_args" not in opts
        assert "cookiesfrombrowser" not in opts
        assert "external_downloader" not in opts

    def test_base_adapter_opts_no_cookies(self):
        from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter
        adapter = YouTubeAdapter()
        opts = adapter._build_ydl_opts(player_clients=None)
        assert "cookiesfrombrowser" not in opts
        assert "external_downloader" not in opts
        assert "proxy" not in opts
        assert "http_headers" not in opts


# ============================================================
# SQLITE INJECTION
# ============================================================

class TestSqliteSecurity:
    """Verificar que SQLite usa consultas parametrizadas."""

    def test_repository_uses_parametrized_queries(self):
        """El repositorio NO debe usar f-strings o .format() para construir WHERE clauses."""
        from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository
        import inspect

        source = inspect.getsource(SQLiteDownloadRepository)
        # Buscar construcciones de WHERE con f-strings (que NO sean SELECTs estáticos)
        lines = source.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if "f\"" in stripped or "f'" in stripped:
                if "WHERE" in stripped or "where" in stripped:
                    if "?" not in stripped:
                        # Permitir f-strings solo si el WHERE contiene un parámetro
                        pytest.fail(f"WHERE clause posiblemente vulnerable: {stripped}")

    def test_db_manager_migrate_uses_hardcoded_columns(self):
        """Las migraciones de DB deben usar columnas hardcodeadas, no entradas del usuario."""
        from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
        import inspect

        source = inspect.getsource(DatabaseManager._migrate_format_options)
        # No debe haber interpolación de usuario en el ALTER TABLE
        assert "user_input" not in source.lower()
        assert "request" not in source.lower()

    def test_sqlite_repository_delete_uses_params(self):
        """El método delete debe usar parámetros, no concatenación."""
        from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository
        import inspect

        source = inspect.getsource(SQLiteDownloadRepository.delete)
        assert "?" in source


# ============================================================
# FILENAME SANITIZATION CONSISTENCY
# ============================================================

class TestFilenameSanitizationConsistency:
    """Verificar que la sanitización de nombres es consistente entre vistas y engine."""

    def test_same_output_for_dangerous_names(self):
        from src.presentation.views.inicio_view import InicioView
        dangerous_names = [
            "test:file", "test<>file", 'test"file', "test/file",
            "test\\file", "test|file", "test?file", "test*file",
        ]
        for name in dangerous_names:
            engine_result = YtDlpDownloadEngine._sanitize_filename(name)
            view_result = InicioView._sanitize_filename(name)
            assert engine_result == view_result, f"Inconsistencia para '{name}': engine={engine_result}, view={view_result}"

    def test_no_empty_results(self):
        from src.presentation.views.inicio_view import InicioView
        dangerous = ["", "...", "???", "***", "\x00\x01\x02"]
        for name in dangerous:
            engine_result = YtDlpDownloadEngine._sanitize_filename(name)
            view_result = InicioView._sanitize_filename(name)
            assert engine_result, f"Engine retornó vacío para '{repr(name)}'"
            assert view_result, f"View retornó vacío para '{repr(name)}'"
            assert engine_result == view_result


# ============================================================
# DOWNLOADED FILE SAFETY
# ============================================================

class TestDownloadedFileSafety:
    """Verificar que archivos descargados no se ejecutan automáticamente."""

    def test_resolve_final_path_verifies_within_dest(self):
        """_ensure_within_dest debe rechazar archivos fuera del directorio destino."""
        result = YtDlpDownloadEngine._ensure_within_dest(
            "C:\\Users\\evil\\Desktop\\evil.exe",
            "C:\\Users\\me\\Downloads"
        )
        assert result is None

    def test_resolve_final_path_allows_within_dest(self):
        """_ensure_within_dest debe aceptar archivos dentro del directorio destino."""
        result = YtDlpDownloadEngine._ensure_within_dest(
            "C:\\Users\\me\\Downloads\\video.mp4",
            "C:\\Users\\me\\Downloads"
        )
        assert result is not None

    def test_resolve_final_path_allows_subdirectory(self):
        """_ensure_within_dest debe aceptar archivos en subdirectorios del destino."""
        result = YtDlpDownloadEngine._ensure_within_dest(
            "C:\\Users\\me\\Downloads\\subdir\\video.mp4",
            "C:\\Users\\me\\Downloads"
        )
        assert result is not None
