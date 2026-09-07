from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter


class GenericAdapter(BasePlatformAdapter):
    """Adaptador de infraestructura genérico para cualquier sitio soportado."""

    def detect(self, url: Url) -> bool:
        return True  # Fallback final para cualquier URL válida

    def analyze(self, url: Url) -> MediaMetadata:
        info = self._extract_with_ytdlp(url)
        detected = url.detect_platform()
        if detected != "Generic":
            platform_name = detected
        else:
            extractor = info.get("extractor_key") or info.get("extractor") or "Generic"
            platform_name = str(extractor).capitalize()
        return self._parse_ytdlp_info(url, info, platform_name=platform_name)
