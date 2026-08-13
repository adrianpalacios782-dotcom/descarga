from typing import List

from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import UnsupportedPlatformError
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.facebook_adapter import FacebookAdapter
from src.infrastructure.adapters.platforms.generic_adapter import GenericAdapter
from src.infrastructure.adapters.platforms.instagram_adapter import InstagramAdapter
from src.infrastructure.adapters.platforms.tiktok_adapter import TikTokAdapter
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter


class PlatformRegistry(IPlatformAdapter):
    """Orquestador/Registro de adaptadores de plataforma (Plugin Strategy)."""

    def __init__(self) -> None:
        self._adapters: List[IPlatformAdapter] = [
            YouTubeAdapter(),
            TikTokAdapter(),
            InstagramAdapter(),
            FacebookAdapter(),
            GenericAdapter(),
        ]

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
