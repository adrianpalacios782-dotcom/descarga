from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter


class TwitchAdapter(BasePlatformAdapter):
    """Adaptador de infraestructura específico para extraer clips, VODs y videos de Twitch."""

    def detect(self, url: Url) -> bool:
        return url.detect_platform() == "Twitch"

    def analyze(self, url: Url) -> MediaMetadata:
        info = self._extract_with_ytdlp(url)
        return self._parse_ytdlp_info(url, info, platform_name="Twitch")
