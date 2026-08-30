"""Cliente HTTP de bajo nivel para el actualizador.

Características de seguridad:
- Solo HTTPS: se rechaza cualquier URL con esquema distinto antes de abrir.
- Allowlist de hosts exactos por tipo de tráfico (metadatos vs assets).
- Guardia de redirecciones: una redirección hacia un host fuera de la
  allowlist aborta la operación (mitiga redirecciones abiertas).
- Sin cookies, sin tokens, sin proxies personalizados; TLS verificado por el
  contexto por defecto (validación de certificados del sistema activa).
"""
from typing import Any
from urllib.parse import urlparse
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    OpenerDirector,
    Request,
    build_opener,
)

import src.infrastructure.updater.update_config as update_config
from src.domain.exceptions.domain_exceptions import UpdateError


class DisallowedRedirectError(UpdateError):
    """Una redirección intentó salir del conjunto de hosts permitidos."""
    pass


class UnsafeUrlError(UpdateError):
    """URL rechazada: esquema u host no permitido por la política."""
    pass


def _url_host_allowed(url: str, allowed_hosts: frozenset[str]) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    return parsed.hostname.lower() in allowed_hosts


class _AllowlistRedirectHandler(HTTPRedirectHandler):
    """Solo sigue redirecciones cuyo destino esté en la allowlist de hosts."""

    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        super().__init__()
        self._allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if not _url_host_allowed(newurl, self._allowed_hosts):
            raise DisallowedRedirectError(
                "Redirección hacia host no permitido bloqueada."
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_safe_opener(allowed_hosts: frozenset[str]) -> OpenerDirector:
    """Construye un opener que solo habla HTTPS y solo navega hosts permitidos."""
    return build_opener(
        _AllowlistRedirectHandler(allowed_hosts),
        HTTPSHandler(),
    )


def validate_url_or_raise(url: str, allowed_hosts: frozenset[str]) -> None:
    """Valida esquema HTTPS y host contra la allowlist; lanza si no cumple."""
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise UnsafeUrlError("URL malformada rechazada.") from exc
    if parsed.scheme != "https":
        raise UnsafeUrlError("Esquema no permitido (solo HTTPS).")
    if not parsed.hostname or parsed.hostname.lower() not in allowed_hosts:
        raise UnsafeUrlError("Host no permitido.")


def open_response(
    url: str,
    allowed_hosts: frozenset[str],
    timeout: float,
) -> Any:
    """Abre una respuesta HTTPS validando URL y siguiendo solo redirecciones seguras.

    Devuelve un objeto similar a http.client.HTTPResponse (context manager).
    Los encabezados anónimos estándar (User-Agent/Accept) se aplican siempre.
    """
    validate_url_or_raise(url, allowed_hosts)
    request = Request(
        url=url,
        headers=dict(update_config.HTTP_HEADERS),
        method="GET",
    )
    opener = build_safe_opener(allowed_hosts)
    return opener.open(request, timeout=timeout)  # noqa: S310 - HTTPS forzado y hosts fijados


def fetch_bytes(
    url: str,
    allowed_hosts: frozenset[str],
    timeout: float,
    max_bytes: int,
) -> bytes:
    """Descarga un payload pequeño completo aplicando cota de tamaño."""
    with open_response(url, allowed_hosts, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UpdateError("El payload remoto excede la cota de tamaño permitida.")
    return bytes(data)
