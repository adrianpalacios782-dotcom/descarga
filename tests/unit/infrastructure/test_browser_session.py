"""Contrato de la sesión de navegador vinculada automáticamente.

La app vincula sola la sesión del navegador detectado, sin que el usuario
cargue un cookies.txt. Este archivo fija el contrato de esa vinculación:

1. **Detección**: se busca un navegador con PERFIL ACTIVO y su almacén de
   cookies (Chromium: ``<perfil>/Network/Cookies``; Firefox:
   ``Profiles/<perfil>/cookies.sqlite``), en el orden Chrome -> Brave -> Edge
   -> Firefox.
2. **Legibilidad**: en Windows, un navegador abierto mantiene su almacén de
   cookies bloqueado (``WinError 32``). La app debe MEDIR esa legibilidad y
   degradar con un aviso, no romperse.
3. **Aplicación**: con almacén legible, las opciones de yt-dlp llevan
   ``cookiesfrombrowser`` y la lista de clientes AUTENTICADA (que incluye
   ``web_creator``, el único que exige iniciar sesión).
4. **Estado**: el resultado viaja hasta la interfaz en ``SessionStatus``.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

import pytest

import src.infrastructure.adapters.platforms.base_platform_adapter as bpa_module
from src.domain.value_objects.session_status import SessionState
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms import browser_detector as bd
from src.infrastructure.adapters.platforms.browser_detector import (
    BrowserSession,
    detect_active_browser_session,
    detect_browser_sessions,
)
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter
from src.infrastructure.adapters.platforms.youtube_client_strategy import (
    ANONYMOUS_FALLBACK_CLIENTS,
    AUTHENTICATED_FALLBACK_CLIENTS,
)


def _chromium_root(root: Path, profiles: Dict[str, bool], last_used: Optional[str] = None) -> Path:
    """Crea una raiz de datos Chromium con los perfiles indicados.

    ``profiles`` mapea nombre de perfil -> legible. El almacén de cookies se
    crea siempre; la legibilidad se simula parcheando ``_is_readable``.
    """
    root.mkdir(parents=True, exist_ok=True)
    if last_used is not None:
        (root / "Local State").write_text(
            json.dumps({"profile": {"last_used": last_used}}), encoding="utf-8"
        )
    for name in profiles:
        db = root / name / "Network" / "Cookies"
        db.parent.mkdir(parents=True, exist_ok=True)
        db.write_bytes(b"SQLite format 3\x00")
    return root


def _firefox_root(root: Path, profiles: Dict[str, bool], default: Optional[str] = None) -> Path:
    """Crea una raiz de datos Firefox con los perfiles indicados."""
    profiles_dir = root / "Profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    for name in profiles:
        db = profiles_dir / name / "cookies.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        db.write_bytes(b"SQLite format 3\x00")
    if default is not None:
        (root / "profiles.ini").write_text(
            "[Profile0]\nName=default-release\nPath=Profiles/default-release\nDefault=1\n",
            encoding="utf-8",
        )
    return root


def _patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirige las rutas de los navegadores a un árbol temporal."""
    base = tmp_path / "browsers"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        bd,
        "_BROWSER_PATHS",
        {
            "chrome": {"win32": [str(base / "chrome")]},
            "brave": {"win32": [str(base / "brave")]},
            "edge": {"win32": [str(base / "edge")]},
            "firefox": {"win32": [str(base / "firefox")]},
        },
    )
    return base


def _patch_readability(monkeypatch: pytest.MonkeyPatch, locked_paths: set) -> None:
    """Marca como bloqueados los almacenes indicados."""
    original = bd._is_readable

    def fake(path: str) -> bool:
        if path in locked_paths:
            return False
        return original(path)

    monkeypatch.setattr(bd, "_is_readable", fake)


class TestChromiumProfileDetection:
    """El perfil activo de Chromium es el que declara ``Local State``."""

    def test_the_active_profile_comes_first(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(base / "chrome", {"Default": True, "Profile 1": True}, last_used="Profile 1")

        sessions = detect_browser_sessions(platform_sys="win32")

        assert sessions, "Debería detectarse el perfil de Chrome"
        assert sessions[0].browser == "chrome"
        assert sessions[0].profile == "Profile 1"

    def test_default_is_used_when_there_is_no_local_state(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(base / "chrome", {"Default": True, "Profile 2": True})

        sessions = detect_browser_sessions(platform_sys="win32")

        assert sessions[0].profile == "Default"

    def test_the_cookie_database_is_located_in_the_network_folder(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(base / "chrome", {"Default": True})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.cookie_db is not None
        assert session.cookie_db.endswith(os.path.join("Network", "Cookies"))

    def test_a_profile_without_cookie_store_is_ignored(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        root = base / "chrome"
        root.mkdir(parents=True, exist_ok=True)
        (root / "Default").mkdir(parents=True, exist_ok=True)

        assert detect_browser_sessions(platform_sys="win32") == []


class TestFirefoxProfileDetection:
    """Firefox usa ``profiles.ini`` para declarar el perfil predeterminado."""

    def test_the_default_profile_comes_first(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _firefox_root(
            base / "firefox",
            {"otro": True, "default-release": True},
            default="default-release",
        )

        sessions = detect_browser_sessions(platform_sys="win32")

        assert sessions, "Debería detectarse el perfil de Firefox"
        assert sessions[0].browser == "firefox"
        assert sessions[0].profile == "default-release"

    def test_the_cookie_database_is_the_sqlite_file(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _firefox_root(base / "firefox", {"default-release": True})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.cookie_db is not None
        assert session.cookie_db.endswith("cookies.sqlite")


class TestBrowserPriority:
    """Orden de prioridad: Chrome -> Brave -> Edge -> Firefox."""

    def test_chrome_wins_over_the_others(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(base / "chrome", {"Default": True})
        _chromium_root(base / "brave", {"Default": True})
        _chromium_root(base / "edge", {"Default": True})
        _firefox_root(base / "firefox", {"default-release": True})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.browser == "chrome"

    def test_brave_wins_over_edge_and_firefox(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(base / "brave", {"Default": True})
        _chromium_root(base / "edge", {"Default": True})
        _firefox_root(base / "firefox", {"default-release": True})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.browser == "brave"

    def test_edge_wins_over_firefox(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(base / "edge", {"Default": True})
        _firefox_root(base / "firefox", {"default-release": True})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.browser == "edge"

    def test_firefox_is_the_last_resort(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _firefox_root(base / "firefox", {"default-release": True})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.browser == "firefox"

    def test_no_browser_returns_none(self, monkeypatch, tmp_path) -> None:
        _patch_paths(monkeypatch, tmp_path)

        assert detect_active_browser_session(platform_sys="win32") is None


class TestReadability:
    """En Windows, el navegador abierto bloquea su almacén de cookies."""

    def test_a_locked_store_is_detected(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(base / "chrome", {"Default": True})
        locked = str(base / "chrome" / "Default" / "Network" / "Cookies")
        _patch_readability(monkeypatch, {locked})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.locked is True
        assert session.usable is False

    def test_a_readable_store_is_usable(self, monkeypatch, tmp_path) -> None:
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(base / "chrome", {"Default": True})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.locked is False
        assert session.usable is True

    def test_a_readable_profile_wins_over_a_locked_one_of_the_same_browser(
        self, monkeypatch, tmp_path
    ) -> None:
        """Del mismo navegador, se prefiere el perfil que se puede leer."""
        base = _patch_paths(monkeypatch, tmp_path)
        _chromium_root(
            base / "chrome", {"Default": True, "Profile 1": True}, last_used="Profile 1"
        )
        locked = str(base / "chrome" / "Profile 1" / "Network" / "Cookies")
        _patch_readability(monkeypatch, {locked})

        session = detect_active_browser_session(platform_sys="win32")

        assert session is not None
        assert session.profile == "Default"
        assert session.usable is True


class TestAutomaticSessionIsApplied:
    """La sesión detectada se aplica a las opciones de yt-dlp."""

    def test_the_session_is_applied_when_the_store_is_readable(self, monkeypatch) -> None:
        session = BrowserSession(browser="chrome", profile="Default", cookie_db="c.db")
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        opts = YouTubeAdapter()._build_ydl_opts()

        assert opts["cookiesfrombrowser"] == ("chrome", "Default")

    def test_a_locked_session_is_not_applied(self, monkeypatch) -> None:
        session = BrowserSession(
            browser="chrome", profile="Default", cookie_db="c.db", locked=True
        )
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        opts = YouTubeAdapter()._build_ydl_opts()

        assert "cookiesfrombrowser" not in opts

    def test_the_session_does_not_replace_a_cookie_file(self, monkeypatch, tmp_path) -> None:
        session = BrowserSession(browser="chrome", profile="Default", cookie_db="c.db")
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

        opts = YouTubeAdapter(cookiefile=str(cookie_file))._build_ydl_opts()

        assert opts["cookiefile"] == str(cookie_file)
        assert "cookiesfrombrowser" not in opts

    def test_the_session_does_not_replace_the_configured_browser(self, monkeypatch) -> None:
        session = BrowserSession(browser="chrome", profile="Default", cookie_db="c.db")
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        opts = YouTubeAdapter(cookies_from_browser="firefox")._build_ydl_opts()

        assert opts["cookiesfrombrowser"] == ("firefox",)

    def test_disabling_the_browser_cookies_removes_the_session(self, monkeypatch) -> None:
        session = BrowserSession(browser="chrome", profile="Default", cookie_db="c.db")
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        opts = YouTubeAdapter()._build_ydl_opts(disable_browser_cookies=True)

        assert "cookiesfrombrowser" not in opts

    def test_the_authenticated_clients_are_used_with_the_session(self, monkeypatch) -> None:
        session = BrowserSession(browser="chrome", profile="Default", cookie_db="c.db")
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        strategies = YouTubeAdapter()._client_strategies()

        assert strategies[0] == AUTHENTICATED_FALLBACK_CLIENTS

    def test_the_anonymous_clients_are_used_without_a_session(self) -> None:
        strategies = YouTubeAdapter()._client_strategies()

        assert strategies[0] == ANONYMOUS_FALLBACK_CLIENTS

    def test_only_youtube_links_the_session_automatically(self, monkeypatch) -> None:
        """El resto de plataformas no cambia de comportamiento."""
        session = BrowserSession(browser="chrome", profile="Default", cookie_db="c.db")
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        from src.infrastructure.adapters.platforms.tiktok_adapter import TikTokAdapter

        opts = TikTokAdapter()._build_ydl_opts()

        assert "cookiesfrombrowser" not in opts


class TestSessionStatus:
    """El estado de la sesión viaja hasta la interfaz."""

    def test_the_status_is_linked_when_the_session_was_applied(self, monkeypatch) -> None:
        session = BrowserSession(browser="chrome", profile="Default", cookie_db="c.db")
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        adapter = YouTubeAdapter()
        adapter._build_ydl_opts()
        status = adapter._build_session_status()

        assert status.state == SessionState.LINKED
        assert status.linked is True
        assert status.browser == "chrome"
        assert status.profile == "Default"

    def test_the_status_is_blocked_when_the_store_is_locked(self, monkeypatch) -> None:
        session = BrowserSession(
            browser="chrome", profile="Default", cookie_db="c.db", locked=True
        )
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        adapter = YouTubeAdapter()
        adapter._build_ydl_opts()
        status = adapter._build_session_status()

        assert status.state == SessionState.BLOCKED
        assert status.blocked is True

    def test_the_status_is_unavailable_without_a_browser(self) -> None:
        status = YouTubeAdapter()._build_session_status()

        assert status.state == SessionState.UNAVAILABLE
        assert status.linked is False

    def test_the_metadata_carries_the_session_status(self, monkeypatch) -> None:
        """El estado llega a la vista a través de ``MediaMetadata``."""
        session = BrowserSession(browser="chrome", profile="Default", cookie_db="c.db")
        monkeypatch.setattr(
            bpa_module, "detect_active_browser_session", lambda *a, **k: session
        )

        class FakeYoutubeDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def close(self):
                pass

            def extract_info(self, url, download=False):
                return {
                    "id": "eUX086mraqc",
                    "title": "Junior H - PARIS [Official Visualizer]",
                    "uploader": "Junior H",
                    "duration": 236.0,
                    "formats": [
                        {
                            "format_id": "137",
                            "ext": "mp4",
                            "height": 1080,
                            "vcodec": "avc1",
                            "acodec": "none",
                        },
                        {
                            "format_id": "140",
                            "ext": "m4a",
                            "vcodec": "none",
                            "acodec": "mp4a",
                            "tbr": 128,
                        },
                    ],
                }

        monkeypatch.setattr(bpa_module.yt_dlp, "YoutubeDL", FakeYoutubeDL)

        metadata = YouTubeAdapter().analyze(
            Url("https://www.youtube.com/watch?v=eUX086mraqc")
        )

        assert metadata.session_status is not None
        assert metadata.session_status.state == SessionState.LINKED
        assert metadata.session_status.browser == "chrome"
