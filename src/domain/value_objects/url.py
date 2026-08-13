from dataclasses import dataclass
from urllib.parse import urlparse
import re

from src.domain.exceptions.domain_exceptions import InvalidUrlError


@dataclass(frozen=True)
class Url:
    """Value Object que representa una URL validada e inmutable."""
    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str):
            raise InvalidUrlError("La URL no puede estar vacía o no ser una cadena válida.")

        cleaned = self.value.strip()
        if not cleaned:
            raise InvalidUrlError("La URL no puede ser una cadena vacía.")

        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise InvalidUrlError(f"Protocolo '{parsed.scheme}' no soportado. Solo se permiten http y https.")

        if not parsed.netloc:
            raise InvalidUrlError("La URL debe contener un dominio o host válido.")

        # Prevención básica de SSRF ante localhost o IPs privadas
        netloc_lower = parsed.netloc.lower()
        if any(host in netloc_lower for host in ("localhost", "127.0.0.1", "0.0.0.0", "::1")):
            raise InvalidUrlError("No se permiten URLs dirigidas a localhost o la red interna.")

        object.__setattr__(self, "value", cleaned)

    def detect_platform(self) -> str:
        """Detecta la plataforma basándose en expresiones regulares del dominio."""
        val = self.value.lower()
        if re.search(r"(youtube\.com|youtu\.be)", val):
            return "YouTube"
        elif re.search(r"(tiktok\.com)", val):
            return "TikTok"
        elif re.search(r"(instagram\.com)", val):
            return "Instagram"
        elif re.search(r"(facebook\.com|fb\.watch)", val):
            return "Facebook"
        return "Generic"

    def __str__(self) -> str:
        return self.value
