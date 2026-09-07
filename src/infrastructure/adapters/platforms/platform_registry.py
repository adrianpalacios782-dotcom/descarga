from typing import List, Optional

from src.domain.entities.media_metadata import MediaMetadata
from src.domain.entities.playlist_metadata import PlaylistMetadata
from src.domain.exceptions.domain_exceptions import UnsupportedPlatformError
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter
from src.infrastructure.adapters.platforms.facebook_adapter import FacebookAdapter
from src.infrastructure.adapters.platforms.generic_adapter import GenericAdapter
from src.infrastructure.adapters.platforms.instagram_adapter import InstagramAdapter
from src.infrastructure.adapters.platforms.kick_adapter import KickAdapter
from src.infrastructure.adapters.platforms.tiktok_adapter import TikTokAdapter
from src.infrastructure.adapters.platforms.twitch_adapter import TwitchAdapter
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter


class PlatformRegistry(IPlatformAdapter):
    """Orquestador/Registro de adaptadores de plataforma (Plugin Strategy)."""

    def __init__(
        self,
        cookies_from_browser: Optional[str] = None,
        cookiefile: Optional[str] = None,
    ) -> None:
        self._adapters: List[IPlatformAdapter] = [
            YouTubeAdapter(cookies_from_browser=cookies_from_browser, cookiefile=cookiefile),
            TikTokAdapter(cookies_from_browser=cookies_from_browser, cookiefile=cookiefile),
            InstagramAdapter(cookies_from_browser=cookies_from_browser, cookiefile=cookiefile),
            FacebookAdapter(cookies_from_browser=cookies_from_browser, cookiefile=cookiefile),
            TwitchAdapter(cookies_from_browser=cookies_from_browser, cookiefile=cookiefile),
            KickAdapter(cookies_from_browser=cookies_from_browser, cookiefile=cookiefile),
            GenericAdapter(cookies_from_browser=cookies_from_browser, cookiefile=cookiefile),
        ]

    def set_cookies_from_browser(self, browser: Optional[str]) -> None:
        """Propaga el navegador de cookies a todos los adaptadores."""
        for adapter in self._adapters:
            if isinstance(adapter, BasePlatformAdapter):
                adapter.cookies_from_browser = (
                    browser.strip() if browser and browser.strip() else None
                )

    def set_cookie_file(self, cookiefile: Optional[str]) -> None:
        """Propaga la ruta del archivo de cookies (cookies.txt) a todos los adaptadores."""
        for adapter in self._adapters:
            if isinstance(adapter, BasePlatformAdapter):
                adapter.set_cookie_file(cookiefile)

    def register_adapter(self, adapter: IPlatformAdapter) -> None:
        """Registra un nuevo adaptador de plataforma en tiempo de ejecución."""
        self._adapters.insert(0, adapter)

    def find_adapter(self, url: Url) -> IPlatformAdapter:
        """Encuentra el adaptador adecuado para procesar la URL."""
        for adapter in self._adapters:
            if adapter.detect(url):
                return adapter
        raise UnsupportedPlatformError(f"No se encontró un adaptador compatible para la URL: {url.value}")

    def detect(self, url: Url) -> bool:
        try:
            adapter = self.find_adapter(url)
            return adapter is not None
        except UnsupportedPlatformError:
            return False

    def analyze(self, url: Url) -> MediaMetadata:
        adapter = self.find_adapter(url)
        return adapter.analyze(url)

    def analyze_playlist(self, url: Url) -> PlaylistMetadata:
        adapter = self.find_adapter(url)
        if isinstance(adapter, BasePlatformAdapter):
            return adapter.analyze_playlist(url)
        raise UnsupportedPlatformError("El adaptador seleccionado no soporta extracción de listas.")
