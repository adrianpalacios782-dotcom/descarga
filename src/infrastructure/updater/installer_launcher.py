"""Lanzamiento seguro del instalador ya verificado.

Responsabilidades:
1. Re-verificación EN DISCO del instalador descargado (tamaño + SHA-256 con
   comparación constant-time). Nunca se ejecuta un archivo `.part`.
2. Bloqueo total fuera de builds empaquetados (modo desarrollo no ejecuta).
3. Lanzamiento desacoplado del instalador en modo silencioso encadenado con
   el reinicio de la aplicación (`cmd /c "...setup.exe /SILENT & start app"`).
4. Utilidades de limpieza de temporales: el directorio se elimina SIEMPRE,
   tanto en éxito como en fallo, y solo si pertenece al patrón propio.
"""
import hashlib
import hmac
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from src.domain.exceptions.domain_exceptions import (
    InvalidUpdateInfoError,
    UpdateError,
    UpdateDownloadError,
)
from src.domain.ports.update_source import RemoteAsset
from src.infrastructure.updater.update_config import (
    MAX_INSTALLER_BYTES,
    TEMP_DIR_PREFIX,
)

logger = logging.getLogger(__name__)

# Flags de lanzamiento: proceso separado sin consola visible ni grupo heredado.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200


def is_frozen_app() -> bool:
    """True cuando se ejecuta desde el binario PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def make_update_tempdir() -> Path:
    """Crea un directorio temporal exclusivo para esta actualización."""
    return Path(tempfile.mkdtemp(prefix=TEMP_DIR_PREFIX))


def cleanup_temp_dir(temp_dir: Path) -> None:
    """Elimina el directorio temporal SOLO si pertenece al patrón propio.

    Protección contra borrados accidentales fuera de %TEMP% o de directorios
    que no fueron creados por el actualizador.
    """
    try:
        path = Path(temp_dir).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if temp_root not in path.parents and path.parent != temp_root:
            return
        if not path.name.startswith(TEMP_DIR_PREFIX):
            return
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            logger.info("Actualización: temporales limpiados (%s).", path.name)
    except OSError:
        pass


def cleanup_stale_update_dirs(max_age_hours: int = 72) -> int:
    """Limpia restos de actualizaciones anteriores abandonadas. Best-effort."""
    removed = 0
    try:
        temp_root = Path(tempfile.gettempdir())
        now = time.time()
        for entry in temp_root.glob(f"{TEMP_DIR_PREFIX}*"):
            if not entry.is_dir():
                continue
            try:
                age_h = (now - entry.stat().st_mtime) / 3600.0
            except OSError:
                continue
            if age_h > max_age_hours:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
    except OSError:
        pass
    return removed


class InstallerLauncher:
    """Verificación final y ejecución del instalador oficial."""

    def __init__(self, popen: Callable[..., object] | None = None) -> None:
        # Inyectable para pruebas: por defecto subprocess.Popen real.
        self._popen = popen or subprocess.Popen

    # ------------------------------------------------------------------ API
    def verify_installer_file(
        self,
        installer_path: Path,
        asset: RemoteAsset,
    ) -> None:
        """Re-verifica el archivo YA descargado leyéndolo íntegramente del disco.

        Defensa en profundidad frente a cualquier hueco entre la descarga y
        la ejecución (p. ej. modificación posterior del temporal).
        """
        if not asset.sha256:
            raise InvalidUpdateInfoError(
                "Sin checksum publicado no se permite verificar el instalador."
            )
        expected_hash = asset.sha256.strip().lower()

        path = Path(installer_path)
        if path.name.endswith(".part"):
            raise UpdateDownloadError(
                "Se intentó verificar una descarga incompleta (.part); operación bloqueada."
            )
        if not path.is_file():
            raise UpdateDownloadError("El instalador descargado no existe.")

        # El instalador debe residir en un directorio temporal propio.
        temp_root = Path(tempfile.gettempdir()).resolve()
        try:
            resolved = path.resolve()
        except OSError as exc:
            raise UpdateDownloadError("No se pudo resolver la ruta del instalador.") from exc
        if resolved.parent.name.startswith(TEMP_DIR_PREFIX) is False or (
            temp_root not in resolved.parents
        ):
            raise UpdateDownloadError(
                "El instalador no reside en el directorio temporal seguro."
            )

        if asset.size_bytes and asset.size_bytes > 0:
            actual_size = resolved.stat().st_size
            if actual_size != asset.size_bytes:
                raise UpdateDownloadError(
                    f"Tamaño incorrecto: {actual_size} != {asset.size_bytes} bytes."
                )

        hasher = hashlib.sha256()
        read_total = 0
        with open(resolved, "rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                read_total += len(chunk)
                hasher.update(chunk)
                if read_total > MAX_INSTALLER_BYTES:
                    raise UpdateDownloadError("Archivo excede el límite de tamaño.")
        if not hmac.compare_digest(hasher.hexdigest(), expected_hash):
            raise UpdateDownloadError(
                "SHA-256 del instalador NO coincide. La ejecución fue bloqueada."
            )

    def install_and_restart(self, installer_path: Path, asset: RemoteAsset) -> None:
        """Verifica y lanza el instalador silencioso; al terminar reinicia la app.

        El comando se construye como línea de comandos VERBATIM para cmd.exe
        (patrón canónico `cmd /c ""prog" args & "prog2""`) evitando el
        re-escape de comillas de list2cmdline, que rompería rutas con espacios.
        """
        self.verify_installer_file(installer_path, asset)

        if not is_frozen_app():
            raise UpdateError(
                "La instalación automática solo está disponible en la versión "
                "instalada de osvaldoDownloaderPro."
            )

        installer = Path(installer_path).resolve()
        app_exe = Path(sys.executable).resolve()
        if not app_exe.is_file():
            raise UpdateError("No se localizó el ejecutable de la aplicación.")

        bat_path = installer.parent / "apply_update.bat"
        bat_content = (
            "@echo off\r\n"
            "ping 127.0.0.1 -n 3 >nul\r\n"
            'taskkill /F /IM osvaldoDownloaderPro.exe >nul 2>&1\r\n'
            "ping 127.0.0.1 -n 2 >nul\r\n"
            f'start /wait "" "{installer}" /SILENT /SUPPRESSMSGBOXES\r\n'
            "ping 127.0.0.1 -n 2 >nul\r\n"
            f'start "" "{app_exe}"\r\n'
            'del "%~f0"\r\n'
        )
        bat_path.write_text(bat_content, encoding="utf-8")

        command_line = f'cmd.exe /c "{bat_path}"'

        logger.info("Actualización: lanzando instalador verificado (silencioso).")
        self._popen(  # noqa: S603 - línea construida solo con rutas verificadas internamente
            command_line,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
        )
