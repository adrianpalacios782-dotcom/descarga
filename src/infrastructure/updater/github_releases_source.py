"""Adaptador oficial de actualizaciones: GitHub Releases API.

- Usa la API JSON oficial (`/releases/latest`), NUNCA scraping del HTML.
- Metadatos solo desde hosts de ALLOWED_METADATA_HOSTS.
- Assets solo desde hosts de ALLOWED_ASSET_HOSTS (con guardia de redirects).
- El nombre del instalador debe cumplir el patrón estricto del proyecto y su
  versión debe coincidir con el tag del release.
- El SHA-256 se resuelve del archivo de checksums publicado en el propio
  release (SHA256SUMS.txt) o del campo `digest` del asset; si ambos existen y
  discrepan se rechaza el release completo.

Las funciones de transporte son inyectables para facilitar pruebas unitarias
sin red real.
"""
import json
import logging
import urllib.error
from typing import Any, Callable

from src.domain.exceptions.domain_exceptions import (
    InvalidUpdateInfoError,
    UpdateError,
)
from src.domain.ports.update_source import IUpdateSource, RemoteAsset, RemoteRelease
from src.infrastructure.updater import http_client, update_config
from src.infrastructure.updater.update_config import (
    ALLOWED_ASSET_HOSTS,
    ALLOWED_METADATA_HOSTS,
    CHECKSUM_ASSET_NAMES,
    CHECKSUM_LINE_PATTERN,
    CONNECT_TIMEOUT_S,
    INSTALLER_ASSET_PATTERN,
    RELEASES_API_URL,
    is_allowed_asset_url,
)

logger = logging.getLogger(__name__)

_MAX_JSON_BYTES = 1024 * 1024
_MAX_CHECKSUM_FILE_BYTES = 256 * 1024


def _default_fetch_json(url: str) -> dict[str, Any]:
    raw = http_client.fetch_bytes(
        url=url,
        allowed_hosts=ALLOWED_METADATA_HOSTS,
        timeout=CONNECT_TIMEOUT_S,
        max_bytes=_MAX_JSON_BYTES,
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidUpdateInfoError("Respuesta de la fuente no es JSON válido.") from exc
    if not isinstance(payload, dict):
        raise InvalidUpdateInfoError("Respuesta de la fuente con estructura inesperada.")
    return payload


def _default_fetch_text(url: str) -> str:
    raw = http_client.fetch_bytes(
        url=url,
        allowed_hosts=ALLOWED_ASSET_HOSTS,
        timeout=CONNECT_TIMEOUT_S,
        max_bytes=_MAX_CHECKSUM_FILE_BYTES,
    )
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - decode con replace no falla
        raise UpdateError("No se pudo decodificar el archivo de checksums.") from exc


class GitHubReleasesSource(IUpdateSource):
    """Consulta el último release estable publicado en el repositorio oficial."""

    def __init__(
        self,
        api_url: str = RELEASES_API_URL,
        fetch_json: Callable[[str], dict[str, Any]] | None = None,
        fetch_text: Callable[[str], str] | None = None,
    ) -> None:
        if not update_config.is_allowed_metadata_url(api_url):
            # Defensa extra: la URL base solo puede apuntar a la API oficial.
            raise InvalidUpdateInfoError("URL de fuente de actualizaciones no permitida.")
        self._api_url = api_url
        self._fetch_json = fetch_json or _default_fetch_json
        self._fetch_text = fetch_text or _default_fetch_text

    # ------------------------------------------------------------------ API
    def get_latest_release(self) -> RemoteRelease:
        try:
            data = self._fetch_json(self._api_url)
        except (InvalidUpdateInfoError, UpdateError):
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpdateError("Fuente de actualizaciones no disponible.") from exc

        tag_name = data.get("tag_name")
        if not isinstance(tag_name, str) or not tag_name.strip():
            raise InvalidUpdateInfoError("El release remoto no declara tag_name válido.")

        notes = data.get("body")
        notes_text = notes.strip() if isinstance(notes, str) else ""

        asset_info = self._select_installer_asset(data, tag_name)
        installer_asset = None
        if asset_info is not None:
            name, url, size, digest_hex = asset_info
            sha256 = self._resolve_sha256(data, name, url, digest_hex)
            installer_asset = RemoteAsset(
                name=name, url=url, size_bytes=size, sha256=sha256
            )

        logger.info(
            "Actualización: release remoto consultado correctamente (tag=%s).",
            tag_name,
        )
        return RemoteRelease(
            tag_name=tag_name.strip(),
            release_notes=notes_text,
            installer_asset=installer_asset,
        )

    # ------------------------------------------------------------- Internos
    @staticmethod
    def _select_installer_asset(
        data: dict[str, Any], tag_name: str
    ) -> tuple[str, str, int | None, str | None] | None:
        """Selecciona el asset instalador de Windows del release.

        Devuelve (nombre, url, tamaño, digest) o None si el release no trae
        instalador (p. ej. release solo de código fuente).
        Lanza InvalidUpdateInfoError si hay candidatos con datos no confiables.
        """
        assets = data.get("assets")
        if assets is None:
            return None
        if not isinstance(assets, list):
            raise InvalidUpdateInfoError("Lista de assets del release malformada.")

        candidates: list[tuple[str, str, int | None, str | None, str]] = []
        for entry in assets:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str):
                continue
            match = INSTALLER_ASSET_PATTERN.match(name)
            if match is None:
                continue

            url = entry.get("browser_download_url")
            if not isinstance(url, str) or not is_allowed_asset_url(url):
                raise InvalidUpdateInfoError(
                    "La URL del instalador no pertenece a la fuente oficial."
                )

            size_raw = entry.get("size")
            size = size_raw if isinstance(size_raw, int) and size_raw > 0 else None

            candidates.append((name, url, size, _digest_from_entry(entry), match.group(1)))

        if not candidates:
            return None

        expected_version = tag_name.strip().lstrip("vV")
        exact = [c for c in candidates if c[4] == expected_version]
        chosen = exact[0] if len(exact) >= 1 else None
        if chosen is None:
            if len(candidates) == 1:
                chosen = candidates[0]
            else:
                raise InvalidUpdateInfoError(
                    "No se pudo asociar de forma inequívoca el instalador al tag del release."
                )

        name, url, size, digest_hex, _version = chosen
        return name, url, size, digest_hex

    def _resolve_sha256(
        self,
        data: dict[str, Any],
        installer_name: str,
        installer_url: str,
        digest_hex: str | None,
    ) -> str | None:
        """Resuelve el SHA-256 publicado para el instalador.

        Orden de confianza: archivo de checksums del release → campo digest.
        Si ambos existen y discrepan, se rechaza la información.
        """
        from_checksum = self._sha256_from_checksum_assets(data, installer_name)

        if from_checksum and digest_hex and from_checksum != digest_hex:
            raise InvalidUpdateInfoError(
                "Los checksum publicados para el instalador discrepan entre sí."
            )

        resolved = from_checksum or digest_hex
        if resolved is None:
            logger.warning(
                "Actualización: el release no publica checksum SHA-256 para %s.",
                installer_name,
            )
        else:
            logger.info(
                "Actualización: checksum SHA-256 disponible para el instalador (url=%s).",
                installer_url,
            )
        return resolved

    def _sha256_from_checksum_assets(self, data: dict[str, Any], installer_name: str) -> str | None:
        assets = data.get("assets")
        if not isinstance(assets, list):
            return None
        result: str | None = None
        for entry in assets:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or name not in CHECKSUM_ASSET_NAMES:
                continue
            url = entry.get("browser_download_url")
            if not isinstance(url, str) or not is_allowed_asset_url(url):
                raise InvalidUpdateInfoError(
                    "La URL del archivo de checksums no pertenece a la fuente oficial."
                )
            try:
                content = self._fetch_text(url)
            except UpdateError:
                raise
            except Exception as exc:
                raise UpdateError(
                    "No se pudo descargar el archivo de checksums del release."
                ) from exc
            found = _extract_sha256_for(content, installer_name)
            if found and result and found != result:
                raise InvalidUpdateInfoError(
                    "El archivo de checksums contiene entradas contradictorias."
                )
            if found:
                result = found
        return result


def _digest_from_entry(entry: dict[str, Any]) -> str | None:
    """Extrae y valida el campo `digest` del asset ('sha256:<hex64>')."""
    digest = entry.get("digest")
    if not isinstance(digest, str) or ":" not in digest:
        return None
    algorithm, _, value = digest.partition(":")
    if algorithm.lower() != "sha256":
        return None
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
        raise InvalidUpdateInfoError("Campo digest del asset malformado.")
    return normalized


def _extract_sha256_for(content: str, installer_name: str) -> str | None:
    """Busca el hash del instalador en un archivo tipo SHA256SUMS.

    Anti path-traversal: se IGNORAN las entradas que contengan separadores de
    ruta (el pipeline oficial publica nombres simples); el nombre se compara
    sin distinción de mayúsculas.
    """
    wanted = installer_name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for line in content.splitlines():
        match = CHECKSUM_LINE_PATTERN.match(line.strip())
        if match is None:
            continue
        hash_hex, listed_name = match.group(1), match.group(2)
        if "/" in listed_name or "\\" in listed_name:
            continue  # nunca confiar en rutas dentro del archivo de checksums
        if listed_name.lower() == wanted:
            return hash_hex.lower()
    return None
