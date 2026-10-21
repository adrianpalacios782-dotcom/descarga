"""Regresión del bug "cookies rápidas borran cookies_from_browser".

Causa raíz: `MainWindow._on_quick_cookies_selected` (botón de cookies rápido de
Inicio) llamaba `apply_settings({"cookies_file": path})`. `apply_settings`
leía `settings.get("cookies_browser")`, que en un dict parcial devuelve None, y
terminaba ejecutando `set_cookies_from_browser(None)` sobre el motor de
descargas y sobre los 7 adaptadores del `PlatformRegistry`: el navegador de
cookies global quedaba vaciado durante toda la sesión (la BD persistida no se
veía afectada, pero sí la sesión en memoria).

Corrección: `apply_settings` es semántico de PRESENCIA (solo toca las claves
presentes en el dict), de modo que un ajuste parcial no puede borrar ajustes
ajenos.
"""

from unittest.mock import MagicMock

from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry
from src.presentation.view_models.main_view_model import MainViewModel


def _make_view_model():
    return MainViewModel(
        platform_adapter=MagicMock(),
        download_engine=MagicMock(),
        repository=MagicMock(),
        event_bus=MagicMock(),
    )


class TestApplySettingsIsPresenceBased:

    def test_quick_cookies_does_not_clear_browser_cookies(self) -> None:
        vm = _make_view_model()
        vm.apply_settings({"cookies_file": "C:/tmp/cookies.txt"})

        vm.download_engine.set_cookies_from_browser.assert_not_called()
        vm.platform_adapter.set_cookies_from_browser.assert_not_called()
        vm.download_engine.set_cookie_file.assert_called_once_with("C:/tmp/cookies.txt")
        vm.platform_adapter.set_cookie_file.assert_called_once_with("C:/tmp/cookies.txt")

    def test_empty_partial_settings_touches_nothing(self) -> None:
        vm = _make_view_model()
        vm.apply_settings({})
        vm.download_engine.set_cookies_from_browser.assert_not_called()
        vm.download_engine.set_cookie_file.assert_not_called()

    def test_explicit_browser_still_applies(self) -> None:
        vm = _make_view_model()
        vm.apply_settings({"cookies_browser": "firefox"})
        vm.download_engine.set_cookies_from_browser.assert_called_once_with("firefox")
        vm.platform_adapter.set_cookies_from_browser.assert_called_once_with("firefox")

    def test_explicit_empty_browser_clears_browser(self) -> None:
        """Guardar la configuración con el combo vaciado debe seguir limpiando."""
        vm = _make_view_model()
        vm.apply_settings({"cookies_browser": "", "cookies_file": ""})
        vm.download_engine.set_cookies_from_browser.assert_called_once_with("")
        vm.download_engine.set_cookie_file.assert_called_once_with("")

    def test_other_settings_are_unaffected_by_presence_semantics(self) -> None:
        vm = _make_view_model()
        vm.apply_settings({"concurrent_fragments": 6, "speed_limit": "50M"})
        vm.download_engine.set_concurrent_fragments.assert_called_once_with(6)
        vm.download_engine.set_rate_limit.assert_called_once_with(50 * 1024 * 1024)


class TestRegistryKeepsBrowserCookies:

    def test_set_cookie_file_does_not_clear_browser_cookies(self) -> None:
        """El registro propaga el archivo de cookies sin tocar el navegador."""
        registry = PlatformRegistry(cookies_from_browser="firefox")
        registry.set_cookie_file("C:/tmp/cookies.txt")
        for adapter in registry._adapters:
            assert adapter.cookies_from_browser == "firefox"

    def test_set_cookies_from_browser_normalizes_empty_to_none(self) -> None:
        registry = PlatformRegistry(cookies_from_browser="firefox")
        registry.set_cookies_from_browser("  ")
        for adapter in registry._adapters:
            assert adapter.cookies_from_browser is None
