"""Descarga segura de miniaturas para previsualización.

Validación aplicada a cada URL (incluidos los saltos de redirección):
- Esquema HTTPS exclusivamente.
- Host no puede ser literal de localhost ni IP privada/loopback/link-local/reservada/multicast.
- Se resuelve el DNS y TODAS las direcciones devueltas deben ser públicas.
- Máximo 3 redirecciones, revalidadas por salto.
- Content-Type debe ser image/*.
- Tamaño máximo acotado (5 MB) tanto por cabecera como por lectura real.
"""

import ipaddress
import socket
import urllib.error
import urllib.request
from typing import Any, List, Optional
from urllib.parse import urlparse


class ThumbnailFetchError(Exception):
    """Fallo genérico al obtener una miniatura."""


class InsecureThumbnailUrlError(ThumbnailFetchError):
    """La URL de la miniatura no supera la validación de seguridad."""


MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_REDIRECTS = 3
CONNECT_TIMEOUT_SECONDS = 10
USER_AGENT = "osvaldoDownloaderPro/1.0"


def _validate_resolved_addresses(hostname: str) -> None:
    """Resuelve el hostname y garantiza que todas las IPs sean públicas."""
    try:
        infos = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
    except OSError as ex:
        raise InsecureThumbnailUrlError(f"No se pudo resolver el host '{hostname}': {ex}") from ex

    if not infos:
        raise InsecureThumbnailUrlError(f"El host '{hostname}' no resolvió a ninguna dirección.")

    for info in infos:
        addr_str = info[4][0]
        try:
            addr = ipaddress.ip_address(addr_str)
        except ValueError:
            raise InsecureThumbnailUrlError(f"Dirección no válida devuelta por DNS: '{addr_str}'")
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise InsecureThumbnailUrlError(
                f"El host '{hostname}' resuelve a una dirección no pública ({addr})."
            )


def validate_thumbnail_url(url_str: str) -> str:
    """Valida una URL de miniatura y la devuelve normalizada. Lanza si es insegura."""
    if not url_str or not isinstance(url_str, str):
        raise InsecureThumbnailUrlError("URL de miniatura vacía.")

    parsed = urlparse(url_str.strip())

    if parsed.scheme != "https":
        raise InsecureThumbnailUrlError("Las miniaturas solo se descargan por HTTPS.")
    if not parsed.hostname:
        raise InsecureThumbnailUrlError("URL de miniatura sin hostname.")
    port = parsed.port
    if port is not None and port != 443:
        raise InsecureThumbnailUrlError("Las miniaturas solo se descargan por el puerto 443.")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in ("localhost", "0.0.0.0", "::1", "0"):
        raise InsecureThumbnailUrlError("No se permiten miniaturas desde localhost.")
    try:
        literal = ipaddress.ip_address(hostname)
        if (
            literal.is_private
            or literal.is_loopback
            or literal.is_link_local
            or literal.is_reserved
            or literal.is_multicast
        ):
            raise InsecureThumbnailUrlError("No se permiten miniaturas desde IPs privadas/reservadas.")
    except ValueError:
        pass  # hostname con nombre: se valida vía DNS abajo.

    _validate_resolved_addresses(hostname)
    return url_str.strip()


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """RedirectHandler que valida cada destino antes de seguirlo."""

    def __init__(self) -> None:
        self.redirects_left = MAX_REDIRECTS

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:  # noqa: D401
        if self.redirects_left <= 0:
            raise ThumbnailFetchError("Demasiadas redirecciones al descargar la miniatura.")
        self.redirects_left -= 1
        validate_thumbnail_url(newurl)
        res = super().redirect_request(req, fp, code, msg, headers, newurl)
        return res


def fetch_thumbnail(url_str: str, timeout: float = CONNECT_TIMEOUT_SECONDS) -> bytes:
    """Descarga los bytes de una miniatura tras validar la URL. Lanza ThumbnailFetchError."""
    safe_url = validate_thumbnail_url(url_str)

    handler = _ValidatingRedirectHandler()
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(
        safe_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/*",
        },
    )

    try:
        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise ThumbnailFetchError(f"Respuesta HTTP {status} al descargar la miniatura.")

            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not content_type.startswith("image/"):
                raise ThumbnailFetchError(
                    f"El contenido remoto no es una imagen (Content-Type: '{content_type or 'desconocido'}')."
                )

            declared_length: Optional[int] = None
            raw_len = response.headers.get("Content-Length")
            if raw_len is not None:
                try:
                    declared_length = int(raw_len)
                except ValueError:
                    declared_length = None
                if declared_length is not None and declared_length > MAX_THUMBNAIL_BYTES:
                    raise ThumbnailFetchError("La miniatura excede el tamaño máximo permitido.")

            chunks: List[bytes] = []
            received = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > MAX_THUMBNAIL_BYTES:
                    raise ThumbnailFetchError("La miniatura excede el tamaño máximo permitido.")
                chunks.append(chunk)
            return b"".join(chunks)
    except urllib.error.URLError as ex:
        raise ThumbnailFetchError(f"Fallo de red al descargar la miniatura: {ex}") from ex
    except ThumbnailFetchError:
        raise
    except Exception as ex:  # pragma: no cover - defensa adicional
        raise ThumbnailFetchError(f"Error inesperado al descargar la miniatura: {ex}") from ex
