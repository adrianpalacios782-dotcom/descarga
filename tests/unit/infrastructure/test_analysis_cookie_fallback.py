"""Contrato de la Capa 2: cookies automáticas en el análisis.

Problema de origen: cuando YouTube bloquea la extracción con un bot-check
("Sign in to confirm you're not a bot") o una restricción de edad, el usuario
sin sesión configurada se queda sin análisis. El motor de descarga ya lo
resolvía reintentando con el navegador detectado; el ANÁLISIS no lo hacía: era
el único hueco.

La Capa 2 cierra ese hueco:

1. Si la extracción falla con un error **recuperable con cookies** (bot-check,
   restricción de edad, "inicia sesión", contenido de miembros, error de
   cookies) y **no hay ninguna cookie configurada**, se reintenta con la sesión
   del navegador detectado automáticamente.
2. Si el navegador está abierto y su almacén de cookies no se puede leer, se
   degrada a calidades públicas en lugar de perder el contenido.
3. El mensaje de error final dice qué se intentó, para que el usuario sepa qué
   hacer.

La clasificación de "recuperable con cookies" NO se reimplementa: se reutiliza
``ErrorClassifier`` (dominio), el mismo que usa el motor de descarga.
"""

from typing import Any, Dict, List, Optional

import pytest

import src.infrastructure.adapters.platforms.base_platform_adapter as bpa_module
from src.domain.exceptions.domain_exceptions import MediaAnalysisError
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter

BOT_CHECK_ERROR = (
    "ERROR: [youtube] eUX086mraqc: Sign in to confirm you're not a bot. "
    "Use --cookies-from-browser or --cookies for the authentication."
)
UNAVAILABLE_ERROR = "ERROR: [youtube] eUX086mraqc: Video unavailable"
DPAPI_ERROR = (
    "ERROR: [youtube] eUX086mraqc: Could not copy cookie jar from "
    "C:\\Users\\test\\AppData\\Local\\Google\\Chrome\\User Data: DPAPI error"
)

FULL_FORMATS = [
    {"format_id": "137", "ext": "mp4", "height": 1080, "vcodec": "avc1", "acodec": "none", "protocol": "https"},
    {"format_id": "248", "ext": "webm", "height": 1080, "vcodec": "vp9", "acodec": "none", "protocol": "https"},
    {"format_id": "140", "ext": "m4a", "height": None, "vcodec": "none", "acodec": "mp4a", "protocol": "https"},
]

PLAYLIST_INFO = {
    "id": "PL123",
    "title": "Mi lista",
    "entries": [
        {"id": "abc123", "title": "Video uno", "duration": 120, "uploader": "Canal"},
    ],
}


def _info(formats: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "id": "eUX086mraqc",
        "title": "Junior H - PARIS [Official Visualizer]",
        "uploader": "Junior H",
        "duration": 180,
        "formats": FULL_FORMATS if formats is None else formats,
    }


class FakeYoutubeDL:
    """Fake de yt_dlp.YoutubeDL que registra las opciones de cada intento.

    Modos:
      - ``ok``: siempre devuelve formatos.
      - ``bot_check``: siempre falla con el error de bot-check.
      - ``bot_check_unless_cookies``: falla con bot-check si no hay cookies;
        con cookies devuelve formatos.
      - ``cookie_read_error``: falla al leer las cookies (navegador abierto) y
        devuelve formatos cuando no hay cookies (escenario de degradación).
      - ``cookie_read_error_always``: falla siempre al leer las cookies, así
        tampoco la degradación a la vía anónima puede rescatarlo.
      - ``unavailable``: falla con "video unavailable" (no recuperable con
        cookies).
      - ``playlist``: devuelve una lista de reproducción.
    """

    def __init__(self, opts: Dict[str, Any], calls: List[Dict[str, Any]], mode: str):
        self.opts = opts
        self.calls = calls
        self.mode = mode

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def close(self) -> None:
        pass

    def extract_info(self, url: str, download: bool = False) -> Dict[str, Any]:
        browser = self.opts.get("cookiesfrombrowser")
        cookiefile = self.opts.get("cookiefile")
        has_cookies = bool(browser or cookiefile)
        self.calls.append(
            {
                "browser": browser[0] if browser else None,
                "cookiefile": cookiefile,
                "anonymous": not has_cookies,
            }
        )
        if self.mode == "ok":
            return _info()
        if self.mode == "bot_check":
            raise RuntimeError(BOT_CHECK_ERROR)
        if self.mode == "bot_check_unless_cookies":
            if not has_cookies:
                raise RuntimeError(BOT_CHECK_ERROR)
            return _info()
        if self.mode == "cookie_read_error":
            if has_cookies:
                raise RuntimeError(DPAPI_ERROR)
            return _info()
        if self.mode == "cookie_read_error_always":
            raise RuntimeError(DPAPI_ERROR)
        if self.mode == "unavailable":
            raise RuntimeError(UNAVAILABLE_ERROR)
        if self.mode == "playlist":
            if not has_cookies:
                raise RuntimeError(BOT_CHECK_ERROR)
            return dict(PLAYLIST_INFO)
        raise RuntimeError(f"modo desconocido: {self.mode}")


def _install(monkeypatch: pytest.MonkeyPatch, mode: str) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    def factory(opts: Dict[str, Any]) -> FakeYoutubeDL:
        return FakeYoutubeDL(opts, calls, mode)

    monkeypatch.setattr(bpa_module.yt_dlp, "YoutubeDL", factory)
    return calls


def _patch_browser(monkeypatch: pytest.MonkeyPatch, browser: Optional[str]) -> None:
    monkeypatch.setattr(bpa_module, "get_first_available_browser", lambda *a, **k: browser)


class TestAutoBrowserRetry:
    """La Capa 2: reintento con la sesión del navegador detectado."""

    def test_analysis_retries_with_the_auto_detected_browser(self, monkeypatch) -> None:
        """Bot-check en la vía anónima -> se reintenta con la sesión del
        navegador y el análisis entrega calidades reales."""
        calls = _install(monkeypatch, "bot_check_unless_cookies")
        _patch_browser(monkeypatch, "chrome")

        metadata = YouTubeAdapter().analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))

        assert metadata.video_quality_options
        assert calls[0]["anonymous"] is True, "La primera pasada debe ser anónima"
        assert calls[-1]["browser"] == "chrome"

    def test_the_retry_uses_the_browser_detected_on_the_machine(self, monkeypatch) -> None:
        calls = _install(monkeypatch, "bot_check_unless_cookies")
        _patch_browser(monkeypatch, "firefox")

        YouTubeAdapter().analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))

        assert calls[-1]["browser"] == "firefox"

    def test_only_the_first_strategy_is_retried_with_cookies(self, monkeypatch) -> None:
        """Reintentar toda la escalera multiplicaría la espera sin aportar nada:
        si el bloqueo es de IP, ningún cliente lo resuelve."""
        calls = _install(monkeypatch, "bot_check")
        _patch_browser(monkeypatch, "chrome")

        with pytest.raises(MediaAnalysisError):
            YouTubeAdapter().analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))

        cookie_calls = [c for c in calls if c["browser"] == "chrome"]
        assert len(cookie_calls) == 1

    def test_no_retry_when_a_cookie_file_is_configured(self, monkeypatch, tmp_path) -> None:
        """El usuario ya aportó su sesión: no se le cambia a escondidas."""
        calls = _install(monkeypatch, "bot_check")
        _patch_browser(monkeypatch, "chrome")
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

        with pytest.raises(MediaAnalysisError):
            YouTubeAdapter(cookiefile=str(cookie_file)).analyze(
                Url("https://www.youtube.com/watch?v=eUX086mraqc")
            )

        assert all(c["browser"] is None for c in calls)
        assert all(c["cookiefile"] == str(cookie_file) for c in calls)

    def test_no_retry_when_a_browser_is_already_configured(self, monkeypatch) -> None:
        """El navegador configurado ya está en uso: no se añade otro."""
        calls = _install(monkeypatch, "bot_check")
        _patch_browser(monkeypatch, "chrome")

        with pytest.raises(MediaAnalysisError):
            YouTubeAdapter(cookies_from_browser="firefox").analyze(
                Url("https://www.youtube.com/watch?v=eUX086mraqc")
            )

        assert all(c["browser"] == "firefox" for c in calls)

    def test_no_retry_for_an_error_that_cookies_cannot_fix(self, monkeypatch) -> None:
        """"Video unavailable" no se arregla con cookies: no debe gastarse una
        request de red extra."""
        calls = _install(monkeypatch, "unavailable")
        _patch_browser(monkeypatch, "chrome")

        with pytest.raises(MediaAnalysisError):
            YouTubeAdapter().analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))

        assert all(c["anonymous"] for c in calls)
        assert not any(c["browser"] for c in calls)


class TestBrowserOpenDegradation:
    """Navegador abierto: se degrada a calidades públicas en vez de fallar."""

    def test_falls_back_to_public_qualities_with_a_warning(self, monkeypatch) -> None:
        calls = _install(monkeypatch, "cookie_read_error")
        _patch_browser(monkeypatch, "chrome")

        metadata = YouTubeAdapter(cookies_from_browser="firefox").analyze(
            Url("https://www.youtube.com/watch?v=eUX086mraqc")
        )

        assert metadata.video_quality_options
        assert metadata.warning_message
        assert "firefox" in metadata.warning_message
        assert any(c["browser"] == "firefox" for c in calls), "Se intentó con cookies"
        assert any(c["anonymous"] for c in calls), "Se reintentó sin cookies"

    def test_the_warning_explains_how_to_unlock_the_high_qualities(self, monkeypatch) -> None:
        _install(monkeypatch, "cookie_read_error")

        metadata = YouTubeAdapter(cookies_from_browser="firefox").analyze(
            Url("https://www.youtube.com/watch?v=eUX086mraqc")
        )

        warning = (metadata.warning_message or "").lower()
        assert "cookies.txt" in warning
        assert "1080p" in warning or "4k" in warning


class TestFinalErrorMessage:
    """El error final debe decir qué se intentó, para que el usuario sepa qué hacer."""

    def test_mentions_the_browser_session_that_was_tried(self, monkeypatch) -> None:
        _install(monkeypatch, "bot_check")
        _patch_browser(monkeypatch, "chrome")

        with pytest.raises(MediaAnalysisError) as ex:
            YouTubeAdapter().analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))

        message = str(ex.value)
        assert "chrome" in message
        assert "cookies.txt" in message

    def test_mentions_that_no_browser_was_found(self, monkeypatch) -> None:
        _install(monkeypatch, "bot_check")
        _patch_browser(monkeypatch, None)

        with pytest.raises(MediaAnalysisError) as ex:
            YouTubeAdapter().analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))

        message = str(ex.value)
        assert "No se encontró ningún navegador" in message
        assert "cookies.txt" in message

    def test_keeps_the_browser_open_guidance(self, monkeypatch) -> None:
        """Si ni siquiera la degradación a la vía anónima funciona, el mensaje
        final sigue explicando que hay que cerrar el navegador."""
        _install(monkeypatch, "cookie_read_error_always")

        with pytest.raises(MediaAnalysisError) as ex:
            YouTubeAdapter(cookies_from_browser="firefox").analyze(
                Url("https://www.youtube.com/watch?v=eUX086mraqc")
            )

        message = str(ex.value)
        assert "firefox" in message
        assert "Cierra el navegador" in message


class TestBrowserOverrideOption:
    """El override de navegador es el mecanismo de la Capa 2 en las opciones."""

    def test_override_takes_priority_over_the_configured_browser(self) -> None:
        opts = YouTubeAdapter(cookies_from_browser="firefox")._build_ydl_opts(
            browser_override="chrome"
        )
        assert opts["cookiesfrombrowser"] == ("chrome",)

    def test_override_is_used_when_nothing_is_configured(self) -> None:
        opts = YouTubeAdapter()._build_ydl_opts(browser_override="chrome")
        assert opts["cookiesfrombrowser"] == ("chrome",)

    def test_disabling_browser_cookies_removes_the_override(self) -> None:
        opts = YouTubeAdapter()._build_ydl_opts(
            browser_override="chrome", disable_browser_cookies=True
        )
        assert "cookiesfrombrowser" not in opts

    def test_override_does_not_replace_a_cookie_file(self, tmp_path) -> None:
        """El archivo de cookies tiene prioridad: es la sesión que el usuario
        eligió explícitamente."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

        opts = YouTubeAdapter(cookiefile=str(cookie_file))._build_ydl_opts(
            browser_override="chrome"
        )

        assert opts["cookiefile"] == str(cookie_file)
        assert "cookiesfrombrowser" not in opts


class TestPlaylistAnalysisAlsoUsesTheFallback:
    """La Capa 2 aplica también al análisis de listas de reproducción."""

    def test_playlist_retries_with_the_auto_detected_browser(self, monkeypatch) -> None:
        calls = _install(monkeypatch, "playlist")
        _patch_browser(monkeypatch, "chrome")

        playlist = YouTubeAdapter().analyze_playlist(
            Url("https://www.youtube.com/playlist?list=PL123")
        )

        assert playlist.entries
        assert calls[-1]["browser"] == "chrome"

    def test_playlist_without_browser_fails_with_a_clear_message(self, monkeypatch) -> None:
        _install(monkeypatch, "bot_check")
        _patch_browser(monkeypatch, None)

        with pytest.raises(MediaAnalysisError) as ex:
            YouTubeAdapter().analyze_playlist(
                Url("https://www.youtube.com/playlist?list=PL123")
            )

        assert "No se pudo analizar la lista" in str(ex.value)
