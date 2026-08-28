from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import UnsupportedPlatformError
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.services.url_sanitizer import sanitize_single_video_url
from src.domain.value_objects.url import Url


class AnalyzeUrlUseCase:
    """Caso de uso para analizar una URL y extraer sus metadatos mediante un adaptador de plataforma."""

    def __init__(self, platform_adapter: IPlatformAdapter) -> None:
        self.platform_adapter = platform_adapter

    def execute(self, url_input: str | Url) -> MediaMetadata:
        raw_str = url_input.value if isinstance(url_input, Url) else str(url_input)
        sanitized_str = sanitize_single_video_url(raw_str)
        url = Url(sanitized_str)

        if not self.platform_adapter.detect(url):
            raise UnsupportedPlatformError(f"La plataforma para la URL '{url.value}' no es soportada por este adaptador.")

        return self.platform_adapter.analyze(url)
