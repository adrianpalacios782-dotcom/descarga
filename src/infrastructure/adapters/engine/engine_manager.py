"""Gestor dinámico del motor yt-dlp.

Mantiene el motor de extracción actualizable INDEPENDIENTEMENTE de la versión
empaquetada con la aplicación:

1. ACTIVACION: si existe una wheel verificada de yt-dlp en
   `%APPDATA%/osvaldoDownloaderPro/engine/`, se antepone a `sys.path` y se
   importa ANTES que cualquier adaptador; si no existe o es invalida, se usa
   el modulo empaquetado como fallback. El contrato es llamar a `activate()`
   al arrancar, antes del primer `import yt_dlp` de la aplicacion.

2. CHEQUEO ASINCRONO: consulta la ultima version publicada (GitHub Releases
   oficial de yt-dlp, con fallback a PyPI JSON API) en un hilo daemon, sin
   bloquear jamas el hilo de la UI. Los resultados se entregan por callbacks.

3. ACTUALIZACION EN SEGUNDO PLANO: descarga la wheel oficial verificando
   SHA-256 obligatorio, cota de tamano, cancelacion y escritura atomica
   (`.part` + renombrado), replicando el protocolo del instalador de la app.
   Una falla del gestor NUNCA impide usar la aplicacion con el motor
   empaquetado.

Seguridad:
- Solo HTTPS con allowlist de hosts fijada en `engine_config`.
- La wheel NUNCA se activa ni ejecuta sin SHA-256 verificado contra la fuente
  oficial en el momento de la descarga.
- El nombre local SIEMPRE se deriva de un nombre validado contra el patron
  estricto de asset (anti path-traversal).
- Las funciones de transporte e importacion son inyectables para pruebas
  unitarias sin red real.
"""
import hashlib
import hmac
import importlib
import json
import logging
import os
import re
import sys
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from src.domain.exceptions.domain_exceptions import (
    InvalidUpdateInfoError,
    UpdateDownloadError,
    UpdateError,
)
from src.infrastructure.adapters.engine import engine_config
from src.infrastructure.updater import http_client

logger = logging.getLogger(__name__)

# Tipo del opener inyectable: (url) -> respuesta tipo HTTPResponse (context manager).
Opener = Callable[[str], Any]
FetchJson = Callable[[str], dict[str, object]]
FetchText = Callable[[str], str]
ImportFn = Callable[[], ModuleType]
ProgressCallback = Callable[[int, int], None]

# Modos de operacion del motor.
MODE_APPDATA_WHEEL = "appdata-wheel"
MODE_PACKAGED = "packaged"

# Fuente de un chequeo de versiones.
SOURCE_GITHUB = "github"
SOURCE_PYPI = "pypi"

_CALENDAR_VERSION_RE = re.compile(
    r"^v?(\d{4})\.(\d{2})\.(\d{2})(?:\.(\d+))?$", re.IGNORECASE
)


@dataclass(frozen=True)
class EngineAsset:
    """Wheel oficial de yt-dlp lista para descargar, ya verificable."""

    filename: str
    url: str
    size_bytes: int | None
    sha256: str


@dataclass(frozen=True)
class EngineUpdateInfo:
    """Resultado de un chequeo de version del motor."""

    latest_version: str
    current_version: str
    update_available: bool
    source: str  # SOURCE_GITHUB | SOURCE_PYPI
    asset: EngineAsset | None


@dataclass(frozen=True)
class EngineStatus:
    """Estado del motor activo tras `activate()`."""

    mode: str  # MODE_APPDATA_WHEEL | MODE_PACKAGED
    version: str
    module_file: str
    wheel_path: str | None


# ================================================================ Versiones
def parse_calendar_version(raw: object) -> tuple[int, ...] | None:
    """Parsea versiones calendario de yt-dlp ('2026.08.19', 'v2023.12.30.1').

    Tolera prefijo v/V y componente opcional de parche. Devuelve None si el
    formato no es valido (a diferencia de SemanticVersion, que exigiria SemVer
    estricto y rechazaria los ceros a la izquierda del calendario).
    """
    if not isinstance(raw, str):
        return None
    match = _CALENDAR_VERSION_RE.match(raw.strip())
    if match is None:
        return None
    return tuple(int(g) for g in match.groups() if g is not None)


def _as_comparable(version: tuple[int, ...]) -> tuple[int, int, int, int]:
    padded = version + (0, 0, 0)
    return (padded[0], padded[1], padded[2], padded[3])


def is_newer_version(candidate: str, current: str) -> bool:
    """True solo si `candidate` es ESTRICTAMENTE superior a `current`.

    Si alguna version no es interpretable devuelve False (politica
    conservadora: nunca actualizar sin una comparacion confiable).
    """
    candidate_parsed = parse_calendar_version(candidate)
    current_parsed = parse_calendar_version(current)
    if candidate_parsed is None or current_parsed is None:
        return False
    return _as_comparable(candidate_parsed) > _as_comparable(current_parsed)


# ================================================================ Transporte por defecto
def _default_fetch_json(url: str) -> dict[str, object]:
    raw = http_client.fetch_bytes(
        url=url,
        allowed_hosts=engine_config.ALLOWED_METADATA_HOSTS,
        timeout=engine_config.CONNECT_TIMEOUT_S,
        max_bytes=engine_config.MAX_JSON_BYTES,
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("Respuesta de la fuente del motor no es JSON valido.") from exc
    if not isinstance(payload, dict):
        raise UpdateError("Fuente del motor con estructura inesperada.")
    return payload


def _default_fetch_text(url: str) -> str:
    raw = http_client.fetch_bytes(
        url=url,
        allowed_hosts=engine_config.ALLOWED_ASSET_HOSTS,
        timeout=engine_config.CONNECT_TIMEOUT_S,
        max_bytes=engine_config.MAX_CHECKSUM_FILE_BYTES,
    )
    return raw.decode("utf-8", errors="replace")


def _default_opener(url: str) -> Any:
    return http_client.open_response(
        url=url,
        allowed_hosts=engine_config.ALLOWED_ASSET_HOSTS,
        timeout=engine_config.DOWNLOAD_READ_TIMEOUT_S,
    )


def _default_import_ytdlp() -> ModuleType:
    return importlib.import_module("yt_dlp")


# ================================================================ Gestor
class EngineManager:
    """Gestiona el ciclo de vida del motor yt-dlp (AppData <-> empaquetado)."""

    def __init__(
        self,
        engine_dir: Path | None = None,
        fetch_json: FetchJson | None = None,
        fetch_text: FetchText | None = None,
        opener: Opener | None = None,
        import_ytdlp: ImportFn | None = None,
    ) -> None:
        self._engine_dir = engine_dir if engine_dir is not None else self._default_engine_dir()
        self._fetch_json = fetch_json or _default_fetch_json
        self._fetch_text = fetch_text or _default_fetch_text
        self._open = opener or _default_opener
        self._import_ytdlp = import_ytdlp or _default_import_ytdlp
        self._status: EngineStatus | None = None
        self._module: ModuleType | None = None
        self._inserted_paths: list[str] = []
        self._install_lock = threading.Lock()

    # ---------------------------------------------------------------- Rutas
    @staticmethod
    def _default_engine_dir() -> Path:
        """Directorio de motor del usuario: %APPDATA%/osvaldoDownloaderPro/engine."""
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / ".osvaldoDownloaderPro"
        return base / "osvaldoDownloaderPro" / "engine"

    def get_engine_dir(self) -> Path:
        """Directorio donde reside/instala la wheel actualizable del motor."""
        return self._engine_dir

    # ------------------------------------------------------------ Activacion
    def find_installed_wheel(self) -> Path | None:
        """Devuelve la wheel mas reciente VALIDA del directorio, o None.

        Valida nombre contra el patron estricto y estructura interna del zip
        (CRC + paquete yt_dlp presente). Nunca lanza hacia fuera.
        """
        try:
            entries = sorted(self._engine_dir.iterdir())
        except OSError:
            return None
        candidates: list[tuple[tuple[int, ...], Path]] = []
        for path in entries:
            if not path.is_file():
                continue
            match = engine_config.WHEEL_ASSET_PATTERN.match(path.name)
            if match is None:
                continue
            version = parse_calendar_version(match.group(1)) or ()
            candidates.append((version, path))
        candidates.sort(key=lambda item: item[0], reverse=True)
        for _version, path in candidates:
            if _is_valid_wheel_package(path):
                return path
        return None

    def activate(self) -> EngineStatus:
        """Activa el mejor motor disponible y devuelve su estado.

        Orden: wheel de AppData (si es valida) -> modulo empaquetado. Debe
        llamarse ANTES de que cualquier adaptador importe yt_dlp; si el modulo
        ya estaba cargado, la wheel no puede reemplazarlo y se avisa en el log.
        """
        was_preloaded = "yt_dlp" in sys.modules
        used_wheel = self.find_installed_wheel()
        module: ModuleType | None = None

        if used_wheel is not None:
            try:
                self._register_sys_path(used_wheel)
                module = self._import_ytdlp()
            except Exception as exc:  # noqa: BLE001 - fallback garantizado
                logger.warning(
                    "Motor: wheel de AppData no utilizable (%s); se usa el empaquetado.",
                    exc.__class__.__name__,
                )
                self._unregister_sys_path()
                module = None
                used_wheel = None

        if module is None:
            module = self._import_ytdlp()

        version_obj = getattr(module, "version", None)
        raw_version = getattr(version_obj, "__version__", "")
        version = raw_version if isinstance(raw_version, str) else ""
        module_file = str(getattr(module, "__file__", "") or "")

        if used_wheel is not None and was_preloaded and not module_file.startswith(
            str(used_wheel)
        ):
            logger.warning(
                "Motor: yt_dlp ya estaba importado al activar; el motor de AppData "
                "(%s) surtira efecto en el proximo arranque.",
                used_wheel.name,
            )

        status = EngineStatus(
            mode=MODE_APPDATA_WHEEL if used_wheel is not None else MODE_PACKAGED,
            version=version,
            module_file=module_file,
            wheel_path=str(used_wheel) if used_wheel is not None else None,
        )
        self._status = status
        self._module = module
        logger.info(
            "Motor activo: modo=%s version=%s (%s).",
            status.mode,
            status.version or "desconocida",
            status.module_file or "sin ruta",
        )
        return status

    def get_active_status(self) -> EngineStatus | None:
        """Estado registrado por la ultima llamada a activate()."""
        return self._status

    def get_active_module(self) -> ModuleType | None:
        """Modulo yt-dlp activo (para extractores que no hagan import propio)."""
        return self._module

    def get_active_version(self) -> str:
        """Version del motor activo; cadena vacia si aun no se activo."""
        if self._status is not None and self._status.version:
            return self._status.version
        try:
            module = self._import_ytdlp()
        except Exception:  # noqa: BLE001 - nunca romper por diagnostico
            return ""
        version_obj = getattr(module, "version", None)
        raw_version = getattr(version_obj, "__version__", "")
        return raw_version if isinstance(raw_version, str) else ""

    def is_using_updated_engine(self) -> bool:
        """True si el motor activo proviene de la wheel actualizable de AppData."""
        return self._status is not None and self._status.mode == MODE_APPDATA_WHEEL

    def _register_sys_path(self, wheel_path: Path) -> None:
        """Antepone la wheel a sys.path, limpiando registros previos propios."""
        self._unregister_sys_path()
        text = str(wheel_path)
        self._inserted_paths.append(text)
        sys.path.insert(0, text)

    def _unregister_sys_path(self) -> None:
        for entry in self._inserted_paths:
            try:
                sys.path.remove(entry)
            except ValueError:
                pass
        self._inserted_paths.clear()

    # ------------------------------------------------------- Chequeo versiones
    def check_for_updates(self) -> EngineUpdateInfo:
        """Consulta sincrona de la ultima version: GitHub primero, PyPI fallback."""
        current = self.get_active_version()
        try:
            info = self._check_github(current)
            logger.info(
                "Motor: chequeo completado via GitHub (remota=%s, actual=%s).",
                info.latest_version,
                current or "?",
            )
            return info
        except Exception as exc:  # noqa: BLE001 - fallback controlado a PyPI
            logger.warning(
                "Motor: fuente GitHub no disponible (%s); probando PyPI.",
                exc.__class__.__name__,
            )
        try:
            return self._check_pypi(current)
        except Exception as exc:  # noqa: BLE001 - contrato: solo errores del dominio
            if isinstance(exc, UpdateError):
                raise
            raise UpdateError("Fuentes de versiones del motor no disponibles.") from exc

    def check_for_updates_async(
        self,
        on_finished: Callable[[EngineUpdateInfo], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> threading.Thread:
        """Chequeo en hilo daemon; entrega resultados por callbacks. No bloquea."""
        def worker() -> None:
            try:
                result = self.check_for_updates()
                if on_finished is not None:
                    on_finished(result)
            except BaseException as exc:  # noqa: BLE001 - jamas rompe el hilo
                logger.warning("Motor: chequeo fallido (%s).", exc.__class__.__name__)
                if on_error is not None:
                    on_error(exc)

        thread = threading.Thread(target=worker, name="engine-check", daemon=True)
        thread.start()
        return thread

    def _check_github(self, current: str) -> EngineUpdateInfo:
        data = self._fetch_json(engine_config.GITHUB_RELEASES_API_URL)
        tag_name = data.get("tag_name")
        if not isinstance(tag_name, str) or not tag_name.strip():
            raise InvalidUpdateInfoError("Release del motor sin tag_name valido.")
        latest = tag_name.strip().lstrip("vV")

        assets = _ensure_asset_list(data.get("assets"))
        asset = self._select_github_wheel_asset(assets)
        return _build_update_info(latest, current, SOURCE_GITHUB, asset)

    def _select_github_wheel_asset(self, assets: list[dict[str, object]]) -> EngineAsset | None:
        chosen: tuple[str, dict[str, object]] | None = None
        for entry in assets:
            name = entry.get("name")
            if not isinstance(name, str):
                continue
            match = engine_config.WHEEL_ASSET_PATTERN.match(name)
            if match is None:
                continue
            url = entry.get("browser_download_url")
            if not isinstance(url, str) or not engine_config.is_allowed_asset_url(url):
                raise InvalidUpdateInfoError(
                    "URL de la wheel fuera de la fuente oficial."
                )
            if chosen is None or _version_of(name) > _version_of(chosen[0]):
                chosen = (name, entry)

        if chosen is None:
            return None
        name, entry = chosen
        sha256 = self._resolve_sha256(assets, name, entry)
        size_raw = entry.get("size")
        size = size_raw if isinstance(size_raw, int) and size_raw > 0 else None
        download_url = entry.get("browser_download_url")
        assert isinstance(download_url, str)  # revalidado arriba
        return EngineAsset(filename=name, url=download_url, size_bytes=size, sha256=sha256)

    def _resolve_sha256(
        self,
        assets: list[dict[str, object]],
        wheel_name: str,
        entry: dict[str, object],
    ) -> str:
        """Resuelve el SHA-256 de la wheel: SHA2-256SUMS o campo digest.

        A diferencia del instalador de la app, aqui el checksum es OBLIGATORIO:
        el motor se instala sin consentimiento explicito del usuario.
        """
        from_checksums = _sha256_from_checksum_assets(assets, wheel_name, self._fetch_text)
        from_digest = _digest_from_entry(entry)
        if from_checksums and from_digest and from_checksums != from_digest:
            raise InvalidUpdateInfoError(
                "Checksums contradictorios para la wheel del motor."
            )
        resolved = from_checksums or from_digest
        if resolved is None:
            raise InvalidUpdateInfoError(
                "La fuente no publica SHA-256 de la wheel: por politica no se descarga."
            )
        return resolved

    def _check_pypi(self, current: str) -> EngineUpdateInfo:
        data = self._fetch_json(engine_config.PYPI_JSON_API_URL)
        info_obj = data.get("info")
        latest = ""
        if isinstance(info_obj, dict):
            raw_version = info_obj.get("version")
            if isinstance(raw_version, str):
                latest = raw_version.strip()
        if not latest:
            raise InvalidUpdateInfoError("PyPI no declara una version valida.")

        urls = _ensure_asset_list(data.get("urls"))
        asset = self._select_pypi_wheel_asset(urls)
        return _build_update_info(latest, current, SOURCE_PYPI, asset)

    def _select_pypi_wheel_asset(self, files: list[dict[str, object]]) -> EngineAsset | None:
        best: tuple[tuple[int, ...], EngineAsset] | None = None
        for entry in files:
            if entry.get("packagetype") != "bdist_wheel":
                continue
            filename = entry.get("filename")
            if not isinstance(filename, str):
                continue
            match = engine_config.WHEEL_ASSET_PATTERN.match(filename)
            if match is None:
                continue
            digests = entry.get("digests")
            sha256 = ""
            if isinstance(digests, dict):
                raw_sha = digests.get("sha256")
                if isinstance(raw_sha, str):
                    sha256 = raw_sha.strip().lower()
            url = entry.get("url")
            if (
                not sha256
                or not isinstance(url, str)
                or not engine_config.is_allowed_asset_url(url)
            ):
                continue
            size_raw = entry.get("size")
            size = size_raw if isinstance(size_raw, int) and size_raw > 0 else None
            candidate_version = parse_calendar_version(match.group(1)) or ()
            asset = EngineAsset(filename=filename, url=url, size_bytes=size, sha256=sha256)
            if best is None or candidate_version > best[0]:
                best = (candidate_version, asset)
        return best[1] if best is not None else None

    # ---------------------------------------------------------- Actualizacion
    def install_update(
        self,
        asset: EngineAsset,
        progress_callback: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Descarga y verifica la wheel en el directorio de motor (atomica).

        Protocolo identico al del instalador de la app: URL validada contra la
        allowlist, SHA-256 incremental obligatorio, cotas de tamano, escritura
        `.part` + fsync y renombrado atomico solo tras verificar todo. Tras el
        exito se eliminan las wheels anteriores.
        """
        with self._install_lock:
            return self._install_locked(asset, progress_callback, cancel_event)

    def _install_locked(
        self,
        asset: EngineAsset,
        progress_callback: ProgressCallback | None,
        cancel_event: threading.Event | None,
    ) -> Path:
        match = engine_config.WHEEL_ASSET_PATTERN.match(asset.filename)
        if match is None:
            raise InvalidUpdateInfoError("Nombre de wheel con formato inesperado.")
        if not engine_config.is_allowed_asset_url(asset.url):
            raise InvalidUpdateInfoError("URL de descarga fuera de la fuente oficial.")
        expected_hash = _normalize_sha256(asset.sha256)

        expected_size = asset.size_bytes if (asset.size_bytes and asset.size_bytes > 0) else None
        if expected_size is not None and expected_size > engine_config.MAX_WHEEL_BYTES:
            raise UpdateDownloadError("El tamano declarado de la wheel excede el limite.")

        try:
            self._engine_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise UpdateDownloadError("No se pudo crear el directorio del motor.") from exc

        target_path = (self._engine_dir / asset.filename).resolve()
        if target_path.parent != self._engine_dir.resolve():
            raise UpdateDownloadError("Ruta local fuera del directorio del motor.")
        part_path = target_path.with_name(target_path.name + ".part")

        hasher = hashlib.sha256()
        downloaded = 0
        try:
            with self._open(asset.url) as response:
                headers = getattr(response, "headers", None)
                content_length = _content_length(headers)
                if content_length is not None and content_length > engine_config.MAX_WHEEL_BYTES:
                    raise UpdateDownloadError("La wheel excede el limite de tamano.")
                total = expected_size if expected_size is not None else content_length or -1

                with open(part_path, "wb") as fh:
                    while True:
                        if cancel_event is not None and cancel_event.is_set():
                            raise UpdateDownloadError("Descarga cancelada por el usuario.")
                        chunk = response.read(engine_config.DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        if downloaded > engine_config.MAX_WHEEL_BYTES:
                            raise UpdateDownloadError(
                                "Descarga abortada: excede el limite de tamano."
                            )
                        if expected_size is not None and downloaded > expected_size:
                            raise UpdateDownloadError(
                                "Descarga abortada: supera el tamano declarado."
                            )
                        fh.write(chunk)
                        hasher.update(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total)

                    fh.flush()
                    os.fsync(fh.fileno())

            if expected_size is not None and downloaded != expected_size:
                raise UpdateDownloadError(
                    f"Descarga incompleta: {downloaded}/{expected_size} bytes."
                )

            actual_hash = hasher.hexdigest()
            if not hmac.compare_digest(actual_hash, expected_hash):
                raise UpdateDownloadError(
                    "Verificacion SHA-256 fallida: la wheel esta danada o manipulada "
                    "y NO sera activada."
                )

            part_path.replace(target_path)  # atomico incluso sobre archivos previos
        except UpdateDownloadError:
            _discard_part(part_path)
            raise
        except Exception as exc:  # noqa: BLE001 - se normaliza a UpdateDownloadError
            _discard_part(part_path)
            raise UpdateDownloadError("Error durante la descarga de la wheel.") from exc

        self._remove_other_wheels(target_path.name)
        logger.info("Motor: wheel %s instalada y verificada.", target_path.name)
        return target_path

    def download_update_async(
        self,
        asset: EngineAsset,
        on_finished: Callable[[Path], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> threading.Thread:
        """Instalacion de la wheel en segundo plano; callbacks desde el hilo worker."""

        def worker() -> None:
            try:
                installed = self.install_update(
                    asset,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                )
                if on_finished is not None:
                    on_finished(installed)
            except BaseException as exc:  # noqa: BLE001 - jamas rompe el hilo
                logger.warning(
                    "Motor: instalacion fallida (%s).", exc.__class__.__name__
                )
                if on_error is not None:
                    on_error(exc)

        thread = threading.Thread(target=worker, name="engine-install", daemon=True)
        thread.start()
        return thread

    def _remove_other_wheels(self, keep_filename: str) -> None:
        """Elimina wheels (o restos .part) distintas a la recien instalada."""
        try:
            for path in self._engine_dir.iterdir():
                if path.name == keep_filename:
                    continue
                is_wheel = engine_config.WHEEL_ASSET_PATTERN.match(path.name) is not None
                is_part = path.name.startswith("yt_dlp-") and path.name.endswith(".whl.part")
                if not (is_wheel or is_part):
                    continue
                try:
                    path.unlink()
                except OSError:
                    logger.debug("Motor: no se pudo eliminar %s.", path.name)
        except OSError:
            pass


# ================================================================ Helpers de modulo
def _is_valid_wheel_package(path: Path) -> bool:
    """Comprueba integridad zip y presencia del paquete yt_dlp dentro."""
    try:
        with zipfile.ZipFile(path) as bundle:
            if bundle.testzip() is not None:
                return False
            names = set(bundle.namelist())
    except (OSError, zipfile.BadZipFile, EOFError):
        return False
    return "yt_dlp/__init__.py" in names and "yt_dlp/version.py" in names


def _normalize_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
        raise InvalidUpdateInfoError("Checksum publicado con formato invalido.")
    return normalized


def _build_update_info(
    latest: str, current: str, source: str, asset: EngineAsset | None
) -> EngineUpdateInfo:
    return EngineUpdateInfo(
        latest_version=latest,
        current_version=current,
        update_available=is_newer_version(latest, current),
        source=source,
        asset=asset,
    )


def _version_of(wheel_filename: str) -> tuple[int, ...]:
    match = engine_config.WHEEL_ASSET_PATTERN.match(wheel_filename)
    if match is None:
        return ()
    return parse_calendar_version(match.group(1)) or ()


def _ensure_asset_list(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        raise InvalidUpdateInfoError("Lista de assets malformada.")
    result: list[dict[str, object]] = []
    for entry in raw:
        if isinstance(entry, dict):
            result.append(entry)
    return result


def _digest_from_entry(entry: dict[str, object]) -> str | None:
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


def _sha256_from_checksum_assets(
    assets: list[dict[str, object]],
    wheel_name: str,
    fetch_text: FetchText,
) -> str | None:
    """Busca el hash de la wheel en los archivos SHA2-256SUMS del release."""
    wanted = wheel_name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    result: str | None = None
    for entry in assets:
        name = entry.get("name")
        if not isinstance(name, str) or name not in engine_config.CHECKSUM_ASSET_NAMES:
            continue
        url = entry.get("browser_download_url")
        if not isinstance(url, str) or not engine_config.is_allowed_asset_url(url):
            raise InvalidUpdateInfoError(
                "URL del archivo de checksums fuera de la fuente oficial."
            )
        try:
            content = fetch_text(url)
        except UpdateError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalizado a UpdateError
            raise UpdateError("No se pudo descargar el archivo de checksums.") from exc
        found = _extract_sha256_for(content, wanted)
        if found and result and found != result:
            raise InvalidUpdateInfoError("El archivo de checksums tiene entradas contradictorias.")
        if found:
            result = found
    return result


def _extract_sha256_for(content: str, wanted_lower: str) -> str | None:
    """Busca `<hex64>  <nombre>` ignorando entradas con separadores de ruta."""
    for line in content.splitlines():
        match = engine_config.CHECKSUM_LINE_PATTERN.match(line.strip())
        if match is None:
            continue
        hash_hex, listed_name = match.group(1), match.group(2)
        if "/" in listed_name or "\\" in listed_name:
            continue  # nunca confiar en rutas dentro del archivo de checksums
        if listed_name.lower() == wanted_lower:
            return hash_hex.lower()
    return None


def _content_length(headers: object) -> int | None:
    if headers is None:
        return None
    raw = getattr(headers, "get", None)
    if not callable(raw):
        return None
    try:
        value = int(str(raw("Content-Length", "")))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _discard_part(part_path: Path) -> None:
    try:
        if part_path.exists():
            part_path.unlink()
    except OSError:
        pass


# ================================================================ Acceso global
_default_manager: EngineManager | None = None


def get_engine_manager() -> EngineManager:
    """Gestor compartido para toda la aplicacion (creacion perezosa)."""
    global _default_manager
    if _default_manager is None:
        _default_manager = EngineManager()
    return _default_manager

