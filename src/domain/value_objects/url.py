from dataclasses import dataclass
from urllib.parse import urlparse
import ipaddress
import re

from src.domain.exceptions.domain_exceptions import InvalidUrlError

# Dominios soportados para descarga de contenido multimedia.
ALLOWED_DOMAINS = (
    "youtube.com", "youtu.be", "m.youtube.com",
    "tiktok.com", "vm.tiktok.com", "www.tiktok.com",
    "instagram.com", "www.instagram.com",
    "facebook.com", "fb.watch", "www.facebook.com", "m.facebook.com",
)


@dataclass(frozen=True)
class Url:
    """Value Object que representa una URL validada e inmutable.

    La validación incluye:
    - Solo http/https
    - Bloqueo de localhost, IPs privadas (IPv4 e IPv6), ranges Link-local
    - Bloqueo de esquemos no soportados (file://, javascript:, etc.)
    - Bloqueo de puertos no estándar
    - Solo dominios de plataformas soportadas
    """
    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str):
            raise InvalidUrlError("La URL no puede estar vacía o no ser una cadena válida.")

        cleaned = self.value.strip()
        if not cleaned:
            raise InvalidUrlError("La URL no puede ser una cadena vacía.")

        parsed = urlparse(cleaned)

        if parsed.scheme not in ("http", "https"):
            raise InvalidUrlError(
                f"Protocolo '{parsed.scheme}' no soportado. Solo se permiten http y https."
            )

        if not parsed.netloc:
            raise InvalidUrlError("La URL debe contener un dominio o host válido.")

        hostname = parsed.hostname or ""
        if not hostname:
            raise InvalidUrlError("La URL debe contener un hostname válido.")

        self._validate_not_localhost(hostname)
        self._validate_not_private_ip(hostname)
        self._validate_not_dangerous_port(parsed.port)
        self._validate_allowed_domain(hostname)

        object.__setattr__(self, "value", cleaned)

    @staticmethod
    def _validate_not_localhost(hostname: str) -> None:
        h = hostname.lower().rstrip(".")
        if h in ("localhost", "0.0.0.0", "::1", "0"):
            raise InvalidUrlError("No se permiten URLs dirigidas a localhost.")

    @staticmethod
    def _validate_not_private_ip(hostname: str) -> None:
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private:
                raise InvalidUrlError(
                    "No se permiten URLs dirigidas a redes privadas."
                )
            if addr.is_loopback:
                raise InvalidUrlError("No se permiten URLs dirigidas a direcciones de loopback.")
            if addr.is_link_local:
                raise InvalidUrlError(
                    "No se permiten URLs dirigidas a redes Link-local."
                )
            if addr.is_reserved:
                raise InvalidUrlError(
                    "No se permiten URLs dirigidas a rangos reservados."
                )
            if addr.is_multicast:
                raise InvalidUrlError(
                    "No se permiten URLs dirigidas a direcciones multicast."
                )
        except InvalidUrlError:
            raise
        except ValueError:
            pass  # hostname no es una IP válida; validación por dominio aplica

    @staticmethod
    def _validate_not_dangerous_port(port: int | None) -> None:
        if port is None:
            return
        ALLOWED_PORTS = {80, 443, 8080, 8443, 554, 1935}
        if port not in ALLOWED_PORTS:
            raise InvalidUrlError(
                f"Puerto {port} no permitido. Solo se permiten puertos estándar de web/video."
            )

    @staticmethod
    def _validate_allowed_domain(hostname: str) -> None:
        h = hostname.lower().rstrip(".")
        for allowed in ALLOWED_DOMAINS:
            if h == allowed or h.endswith("." + allowed):
                return
        raise InvalidUrlError(
            f"El dominio '{hostname}' no pertenece a una plataforma soportada."
        )

    def detect_platform(self) -> str:
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
