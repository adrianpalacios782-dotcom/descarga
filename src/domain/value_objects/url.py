from dataclasses import dataclass
from urllib.parse import urlparse
import ipaddress

from src.domain.exceptions.domain_exceptions import InvalidUrlError

# Dominios soportados para descarga de contenido multimedia.
ALLOWED_DOMAINS = (
    "youtube.com", "youtu.be", "m.youtube.com",
    "tiktok.com", "vm.tiktok.com", "www.tiktok.com",
    "instagram.com", "www.instagram.com",
    "facebook.com", "fb.watch", "www.facebook.com", "m.facebook.com",
    "twitch.tv", "clips.twitch.tv", "www.twitch.tv", "m.twitch.tv",
    "kick.com", "www.kick.com",
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
        """Valida que el host corresponda a un dominio público seguro (prevención anti-SSRF)."""
        Url._validate_public_domain(hostname)

    @staticmethod
    def _validate_public_domain(hostname: str) -> None:
        """Valida que el host sea un FQDN o IP pública válida, bloqueando redes internas o no enrutables."""
        h = hostname.lower().rstrip(".")
        if not h:
            raise InvalidUrlError("El hostname no puede estar vacío.")

        # Si es una dirección IP válida, _validate_not_private_ip ya confirmó que no es privada ni reservada.
        try:
            ipaddress.ip_address(h)
            return
        except ValueError:
            pass

        # Para dominios: debe contener al menos un punto para evitar hosts de intranet/LAN (ej. http://intranet/)
        if "." not in h:
            raise InvalidUrlError(
                f"El host '{hostname}' no es un dominio público válido (debe contener un TLD)."
            )

        if len(h) > 253:
            raise InvalidUrlError("El nombre de dominio excede la longitud máxima permitida (253 caracteres).")

        labels = h.split(".")
        tld = labels[-1]

        # Bloquear TLDs reservados para redes locales o pruebas (RFC 6761, RFC 8375)
        RESERVED_TLDS = {
            "local", "localhost", "internal", "lan", "home", "corp",
            "arpa", "test", "example", "invalid", "onion",
        }
        if tld in RESERVED_TLDS:
            raise InvalidUrlError(
                f"El dominio '{hostname}' utiliza un TLD reservado o de red interna no permitido."
            )

        import re
        for label in labels:
            if not label:
                raise InvalidUrlError(
                    f"El dominio '{hostname}' contiene etiquetas vacías no válidas."
                )
            if len(label) > 63:
                raise InvalidUrlError(
                    f"La etiqueta de dominio '{label}' excede los 63 caracteres máximos."
                )
            if label.startswith("-") or label.endswith("-"):
                raise InvalidUrlError(
                    f"La etiqueta de dominio '{label}' no puede empezar ni terminar con guión."
                )
            if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", label):
                raise InvalidUrlError(
                    f"La etiqueta de dominio '{label}' contiene caracteres no permitidos."
                )

        # Validar formato del TLD (alfabético o punycode de al menos 2 caracteres)
        if not (re.match(r"^[a-z]{2,}$", tld) or tld.startswith("xn--")):
            raise InvalidUrlError(
                f"El TLD '{tld}' no es un dominio de nivel superior público válido."
            )

    def detect_platform(self) -> str:
        parsed = urlparse(self.value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        if host in ("youtube.com", "youtu.be", "m.youtube.com") or host.endswith(".youtube.com"):
            return "YouTube"
        elif host in ("tiktok.com", "vm.tiktok.com") or host.endswith(".tiktok.com"):
            return "TikTok"
        elif host in ("instagram.com",) or host.endswith(".instagram.com"):
            return "Instagram"
        elif host in ("facebook.com", "fb.watch", "m.facebook.com") or host.endswith(".facebook.com"):
            return "Facebook"
        elif host in ("twitch.tv", "clips.twitch.tv", "m.twitch.tv") or host.endswith(".twitch.tv"):
            return "Twitch"
        elif host in ("kick.com",) or host.endswith(".kick.com"):
            return "Kick"
        elif host in ("twitter.com", "x.com", "t.co") or host.endswith(".twitter.com") or host.endswith(".x.com"):
            return "Twitter"
        elif host in ("reddit.com", "v.redd.it") or host.endswith(".reddit.com"):
            return "Reddit"
        elif host in ("vimeo.com", "player.vimeo.com") or host.endswith(".vimeo.com"):
            return "Vimeo"
        elif host in ("soundcloud.com", "snd.sc") or host.endswith(".soundcloud.com"):
            return "SoundCloud"
        elif host in ("pinterest.com", "pin.it") or host.endswith(".pinterest.com"):
            return "Pinterest"
        elif host in ("dailymotion.com", "dai.ly") or host.endswith(".dailymotion.com"):
            return "Dailymotion"
        elif host in ("bilibili.com", "b23.tv") or host.endswith(".bilibili.com"):
            return "Bilibili"
        elif host in ("bsky.app",) or host.endswith(".bsky.app"):
            return "Bluesky"
        elif host in ("threads.net",) or host.endswith(".threads.net"):
            return "Threads"
        return "Generic"

    def is_playlist(self) -> bool:
        """Determina si la URL corresponde a una lista de reproducción."""
        return is_playlist(self.value)

    def __str__(self) -> str:
        return self.value


def is_playlist(url_str: str) -> bool:
    """Función de utilidad para detectar URLs de playlists o álbumes."""
    if not url_str:
        return False
    parsed = urlparse(url_str.strip())
    path = parsed.path.lower()
    query = parsed.query.lower()
    if "list=" in query:
        return True
    if any(path.startswith(p) for p in ("/playlist", "/sets/", "/album/")):
        return True
    return False

