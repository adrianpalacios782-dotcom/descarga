"""Descarga segura del instalador de actualización.

Protocolo anti-ejecución-de-basura:
1. Se valida la URL del asset contra la allowlist oficial (HTTPS + hosts).
2. El nombre local se deriva SIEMPRE de un nombre fijo interno saneado
   (nunca del servidor) y se resuelve dentro del directorio temporal.
3. La descarga va a un archivo `.part` dentro de un directorio temporal
   exclusivo; NUNCA sobre archivos de la aplicación.
4. Mientras se descarga se calcula el SHA-256 incrementalmente y se verifica:
   - tamaño exacto esperado (si se declaró en el release),
   - cota máxima absoluta,
   - integridad de cierre (sin truncamientos).
5. Solo si TODO verifica, se renombra atómico `.part` → nombre final.
6. El caller es responsable de limpiar el directorio temporal (el launcher lo
   hace siempre en éxito o fallo).

La función de transporte (`opener`) es inyectable para pruebas sin red.
"""
import hashlib
import hmac
import os
import threading
from pathlib import Path
from typing import Any, Callable

from src.domain.exceptions.domain_exceptions import (
    InvalidUpdateInfoError,
    UpdateDownloadError,
)
from src.domain.ports.update_source import RemoteAsset
from src.infrastructure.updater import http_client, update_config

# Tipo del opener inyectable: (url) -> respuesta tipo HTTPResponse (context manager).
Opener = Callable[[str], Any]


def _default_opener(url: str) -> Any:
    return http_client.open_response(
        url=url,
        allowed_hosts=update_config.ALLOWED_ASSET_HOSTS,
        timeout=update_config.DOWNLOAD_READ_TIMEOUT_S,
    )


class InstallerDownloader:
    """Descarga el instalador remoto a un temporal seguro y devuelve su ruta."""

    def __init__(self, opener: Opener | None = None) -> None:
        self._open = opener or _default_opener

    # ------------------------------------------------------------------ API
    def download_to_tempdir(
        self,
        asset: RemoteAsset,
        temp_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Descarga `asset` dentro de `temp_dir` verificando tamaño y SHA-256.

        - `temp_dir` debe existir y ser exclusivo para esta descarga.
        - Si el asset no declara sha256 se lanza InvalidUpdateInfoError:
          la política del proyecto es NO ejecutar archivos no verificados.
        - Si `cancel_event` se activa a mitad de descarga, se aborta y se
          elimina el `.part` (cancelación del usuario).

        Devuelve la ruta final verificada (ya sin extensión .part).
        """
        if not update_config.is_allowed_asset_url(asset.url):
            raise InvalidUpdateInfoError("URL de descarga fuera de la fuente oficial.")

        if not asset.sha256:
            raise InvalidUpdateInfoError(
                "El release no publica checksum SHA-256: por política no se "
                "descarga ni ejecuta un instalador no verificable."
            )
        expected_hash = self._normalize_sha256(asset.sha256)

        target_path = self._safe_local_path(temp_dir, update_config.LOCAL_INSTALLER_FILENAME)
        part_path = target_path.with_name(target_path.name + ".part")

        expected_size = asset.size_bytes if (asset.size_bytes and asset.size_bytes > 0) else None
        if expected_size is not None and expected_size > update_config.MAX_INSTALLER_BYTES:
            raise UpdateDownloadError("El tamaño declarado del instalador excede el límite.")

        hasher = hashlib.sha256()
        downloaded = 0

        try:
            with self._open(asset.url) as response:
                # Tamaño según el servidor; si discrepa del manifest se usa el
                # manifest como referencia pero se cota igualmente.
                headers = getattr(response, "headers", None)
                content_length = None
                if headers is not None:
                    try:
                        content_length = int(headers.get("Content-Length", ""))
                    except (TypeError, ValueError):
                        content_length = None
                if content_length is not None and content_length > update_config.MAX_INSTALLER_BYTES:
                    raise UpdateDownloadError("El instalador excede el límite de tamaño.")

                total = expected_size or (
                    content_length if content_length is not None else -1
                )

                with open(part_path, "wb") as fh:
                    while True:
                        if cancel_event is not None and cancel_event.is_set():
                            raise UpdateDownloadError(
                                "Descarga cancelada por el usuario."
                            )
                        chunk = response.read(update_config.DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        if downloaded > update_config.MAX_INSTALLER_BYTES:
                            raise UpdateDownloadError(
                                "Descarga abortada: excede el límite de tamaño."
                            )
                        if expected_size is not None and downloaded > expected_size:
                            raise UpdateDownloadError(
                                "Descarga abortada: supera el tamaño declarado."
                            )
                        fh.write(chunk)
                        hasher.update(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total)

                    fh.flush()
                    os.fsync(fh.fileno())

            # --- Verificación 1: tamaño exacto ---------------------------
            if expected_size is not None and downloaded != expected_size:
                raise UpdateDownloadError(
                    f"Descarga incompleta: {downloaded}/{expected_size} bytes."
                )
            actual_size = part_path.stat().st_size
            if expected_size is not None and actual_size != expected_size:
                raise UpdateDownloadError("Tamaño en disco no coincide con el esperado.")

            # --- Verificación 2: SHA-256 ---------------------------------
            actual_hash = hasher.hexdigest()
            if not hmac.compare_digest(actual_hash, expected_hash):
                raise UpdateDownloadError(
                    "Verificación SHA-256 fallida: el instalador está dañado o "
                    "manipulado y NO será ejecutado."
                )

            # --- Renombrado atómico solo tras verificar todo --------------
            if target_path.exists():
                target_path.unlink()
            part_path.rename(target_path)

        except UpdateDownloadError:
            self._discard_part(part_path)
            raise
        except Exception as exc:
            self._discard_part(part_path)
            raise UpdateDownloadError("Error durante la descarga del instalador.") from exc

        return target_path

    # ------------------------------------------------------------- Internos
    @staticmethod
    def _normalize_sha256(value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            raise InvalidUpdateInfoError("Checksum publicado con formato inválido.")
        return normalized

    @staticmethod
    def _safe_local_path(temp_dir: Path, filename: str) -> Path:
        """Resuelve `filename` dentro de `temp_dir` bloqueando path traversal."""
        clean = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if clean in ("", ".", "..") or any(c in clean for c in ':*?"<>|'):
            raise UpdateDownloadError("Nombre de archivo local inválido.")
        candidate = (Path(temp_dir) / clean).resolve()
        base = Path(temp_dir).resolve()
        if candidate.parent != base:
            raise UpdateDownloadError("Ruta local fuera del directorio temporal.")
        return candidate

    @staticmethod
    def _discard_part(part_path: Path) -> None:
        try:
            if part_path.exists():
                part_path.unlink()
        except OSError:
            pass
