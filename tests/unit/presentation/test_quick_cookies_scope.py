"""Alcance (scope) del boton de cookies rapido de Inicio.

Regresion del bug "el boton de cookies rapido muta la configuracion de cookies
de TODOS los adaptadores":

`MainWindow._on_quick_cookies_selected` llama a
`apply_settings({"cookies_file": path})`. `PlatformRegistry.set_cookie_file`
propaga ese archivo a los 7 adaptadores registrados, de modo que cargar un
cookies.txt para una plataforma reescribia el `cookiefile` de las demas
(incluidos los que ya tenian su propio archivo configurado).

Correccion: `PlatformRegistry.set_cookie_file_scoped(cookiefile, url)` aplica
el archivo SOLO al adaptador que corresponde a la URL, y el ViewModel lo usa
cuando conoce la URL que se esta analizando. El resto de adaptadores
conservan intactos tanto su `cookiefile` como su `cookies_from_browser`
(que es un ajuste global independiente, no se toca).
"""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple, cast
from unittest.mock import MagicMock

from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry
from src.presentation.main_window import MainWindow
from src.presentation.view_models.main_view_model import MainViewModel

YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
TIKTOK_URL = "https://www.tiktok.com/@usuario/video/1234567890"
INVALID_URL = "no-es-una-url"


def _make_view_model(platform_adapter=None):
    return MainViewModel(
        platform_adapter=platform_adapter if platform_adapter is not None else MagicMock(),
        download_engine=MagicMock(),
        repository=MagicMock(),
        event_bus=MagicMock(),
    )


class TestRegistryScopedCookieFile:

    def test_scoped_applies_only_to_the_adapter_of_the_url(self) -> None:
        registry = PlatformRegistry(cookies_from_browser="firefox")
        registry.set_cookie_file("C:/tmp/previo.txt")

        ok = registry.set_cookie_file_scoped("C:/tmp/nuevo.txt", YOUTUBE_URL)

        assert ok is True
        adaptador_youtube = registry.find_adapter(Url(YOUTUBE_URL))
        assert adaptador_youtube.cookiefile == "C:/tmp/nuevo.txt"

        for adaptador in registry._adapters:
            if adaptador is adaptador_youtube:
                continue
            assert adaptador.cookiefile == "C:/tmp/previo.txt", (
                "El alcance del boton de cookies rapido no debe tocar los demas adaptadores"
            )

    def test_scoped_never_clears_cookies_from_browser(self) -> None:
        registry = PlatformRegistry(cookies_from_browser="firefox")
        registry.set_cookie_file_scoped("C:/tmp/nuevo.txt", YOUTUBE_URL)

        for adaptador in registry._adapters:
            assert adaptador.cookies_from_browser == "firefox"

    def test_scoped_returns_false_for_invalid_url(self) -> None:
        registry = PlatformRegistry()
        registry.set_cookie_file("C:/tmp/previo.txt")

        ok = registry.set_cookie_file_scoped("C:/tmp/nuevo.txt", INVALID_URL)

        assert ok is False
        for adaptador in registry._adapters:
            assert adaptador.cookiefile == "C:/tmp/previo.txt"

    def test_global_set_cookie_file_still_propagates_to_all(self) -> None:
        """El guardado de la configuracion global sigue siendo global."""
        registry = PlatformRegistry()
        registry.set_cookie_file("C:/tmp/global.txt")
        for adaptador in registry._adapters:
            assert adaptador.cookiefile == "C:/tmp/global.txt"


class TestViewModelCookieScope:

    def test_scoped_url_only_reaches_the_matching_adapter(self) -> None:
        registry = PlatformRegistry(cookies_from_browser="firefox")
        registry.set_cookie_file("C:/tmp/previo.txt")
        vm = _make_view_model(platform_adapter=registry)

        vm.apply_settings({"cookies_file": "C:/tmp/nuevo.txt"}, scope_url=YOUTUBE_URL)

        adaptador_youtube = registry.find_adapter(Url(YOUTUBE_URL))
        adaptador_tiktok = registry.find_adapter(Url(TIKTOK_URL))

        assert adaptador_youtube.cookiefile == "C:/tmp/nuevo.txt"
        assert adaptador_tiktok.cookiefile == "C:/tmp/previo.txt"

    def test_scoped_url_does_not_clear_browser_cookies(self) -> None:
        registry = PlatformRegistry(cookies_from_browser="firefox")
        vm = _make_view_model(platform_adapter=registry)

        vm.apply_settings({"cookies_file": "C:/tmp/nuevo.txt"}, scope_url=YOUTUBE_URL)

        for adaptador in registry._adapters:
            assert adaptador.cookies_from_browser == "firefox"

    def test_engine_still_receives_the_cookie_file(self) -> None:
        """El motor de descargas es global: el archivo se aplica igual."""
        registry = PlatformRegistry()
        vm = _make_view_model(platform_adapter=registry)

        vm.apply_settings({"cookies_file": "C:/tmp/nuevo.txt"}, scope_url=YOUTUBE_URL)

        vm.download_engine.set_cookie_file.assert_called_once_with("C:/tmp/nuevo.txt")
        vm.download_engine.set_cookies_from_browser.assert_not_called()

    def test_without_scope_url_the_behaviour_is_unchanged(self) -> None:
        """Sin URL de referencia se mantiene el comportamiento global anterior."""
        vm = _make_view_model()

        vm.apply_settings({"cookies_file": "C:/tmp/cookies.txt"})

        vm.platform_adapter.set_cookie_file.assert_called_once_with("C:/tmp/cookies.txt")

    def test_falls_back_to_global_when_scope_url_is_invalid(self) -> None:
        registry = PlatformRegistry()
        vm = _make_view_model(platform_adapter=registry)

        vm.apply_settings({"cookies_file": "C:/tmp/nuevo.txt"}, scope_url=INVALID_URL)

        for adaptador in registry._adapters:
            assert adaptador.cookiefile == "C:/tmp/nuevo.txt"


class _FakeUrlInput:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _FakeInicioView:
    def __init__(self, url: str) -> None:
        self.url_input = _FakeUrlInput(url)


class _FakeViewModel:
    def __init__(self) -> None:
        self.calls: List[Tuple[Dict[str, Any], Optional[str]]] = []
        self.analyzed: List[str] = []

    def apply_settings(
        self,
        settings: Dict[str, Any],
        scope_url: Optional[str] = None,
    ) -> None:
        self.calls.append((settings, scope_url))

    def analyze_url(self, url: str) -> None:
        self.analyzed.append(url)


class TestMainWindowQuickCookies:

    def test_quick_cookies_passes_the_current_url_as_scope(self) -> None:
        vm = _FakeViewModel()
        stub = SimpleNamespace(view_model=vm, inicio_view=_FakeInicioView(YOUTUBE_URL))

        MainWindow._on_quick_cookies_selected(cast(Any, stub), "C:/tmp/cookies.txt")

        assert vm.calls == [({"cookies_file": "C:/tmp/cookies.txt"}, YOUTUBE_URL)]
        assert vm.analyzed == [YOUTUBE_URL]

    def test_quick_cookies_without_url_has_no_scope(self) -> None:
        vm = _FakeViewModel()
        stub = SimpleNamespace(view_model=vm, inicio_view=_FakeInicioView("   "))

        MainWindow._on_quick_cookies_selected(cast(Any, stub), "C:/tmp/cookies.txt")

        assert vm.calls == [({"cookies_file": "C:/tmp/cookies.txt"}, None)]
        assert vm.analyzed == []
