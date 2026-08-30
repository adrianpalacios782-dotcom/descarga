import threading
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter
from src.infrastructure.adapters.platforms.generic_adapter import GenericAdapter
from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry


def test_download_engine_cookies_opts_injection():
    engine = YtDlpDownloadEngine(cookies_from_browser="chrome")
    assert engine.cookies_from_browser == "chrome"

    cancel = threading.Event()
    pause = threading.Event()
    opts = engine._build_base_opts("out.mp4", "task-1", cancel, pause)
    assert opts.get("cookiesfrombrowser") == ("chrome",)

    # Cambiar navegador dinámicamente
    engine.set_cookies_from_browser("firefox")
    assert engine.cookies_from_browser == "firefox"
    opts2 = engine._build_base_opts("out.mp4", "task-1", cancel, pause)
    assert opts2.get("cookiesfrombrowser") == ("firefox",)

    # Desactivar
    engine.set_cookies_from_browser("")
    assert engine.cookies_from_browser is None
    opts3 = engine._build_base_opts("out.mp4", "task-1", cancel, pause)
    assert "cookiesfrombrowser" not in opts3


def test_base_platform_adapter_cookies_opts():
    adapter = GenericAdapter(cookies_from_browser="edge")
    opts = adapter._build_ydl_opts()
    assert opts.get("cookiesfrombrowser") == ("edge",)

    adapter.cookies_from_browser = None
    opts2 = adapter._build_ydl_opts()
    assert "cookiesfrombrowser" not in opts2


def test_platform_registry_propagates_cookies():
    registry = PlatformRegistry(cookies_from_browser="brave")
    for adapter in registry._adapters:
        if isinstance(adapter, BasePlatformAdapter):
            assert adapter.cookies_from_browser == "brave"

    registry.set_cookies_from_browser("chrome")
    for adapter in registry._adapters:
        if isinstance(adapter, BasePlatformAdapter):
            assert adapter.cookies_from_browser == "chrome"

    registry.set_cookies_from_browser(None)
    for adapter in registry._adapters:
        if isinstance(adapter, BasePlatformAdapter):
            assert adapter.cookies_from_browser is None
