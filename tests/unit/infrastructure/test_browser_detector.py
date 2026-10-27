"""Tests para la detección de navegadores en el sistema."""
from unittest.mock import patch

from src.infrastructure.adapters.platforms.browser_detector import (
    SESSION_BROWSER_ORDER,
    detect_installed_browsers,
    get_first_available_browser,
)


def test_detect_installed_browsers_with_mocks() -> None:
    def fake_isdir(path: str) -> bool:
        return "Chrome" in path or "Firefox" in path

    with patch("os.path.isdir", side_effect=fake_isdir):
        browsers = detect_installed_browsers(platform_sys="win32")
        assert "chrome" in browsers
        assert "firefox" in browsers
        assert "edge" not in browsers


def test_get_first_available_browser_honors_preferred() -> None:
    with patch(
        "src.infrastructure.adapters.platforms.browser_detector.detect_installed_browsers",
        return_value=["chrome", "firefox", "edge"],
    ):
        assert get_first_available_browser("edge") == "edge"
        assert get_first_available_browser() == "chrome"  # según orden preferido


def test_the_session_order_is_chrome_brave_edge_firefox() -> None:
    """Orden pedido para vincular la sesión automáticamente."""
    assert SESSION_BROWSER_ORDER == ["chrome", "brave", "edge", "firefox"]


def test_get_first_available_browser_none_when_empty() -> None:
    with patch(
        "src.infrastructure.adapters.platforms.browser_detector.detect_installed_browsers",
        return_value=[],
    ):
        assert get_first_available_browser() is None
