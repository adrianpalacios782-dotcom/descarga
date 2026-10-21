import logging
import os
import shutil
from typing import Any, Dict, List, Optional, Set
import yt_dlp
import re

from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.entities.playlist_metadata import PlaylistEntry, PlaylistMetadata
from src.domain.services.format_normalizer import FormatNormalizer
from src.domain.exceptions.domain_exceptions import MediaAnalysisError
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.media.subtitle_extractor import extract_subtitle_tracks

logger = logging.getLogger(__name__)

# Cache perezoso de los player_client soportados por la version de yt-dlp instalada.
# Permite descartar nombres obsoletos (p. ej. "tv_embedded", que ya no existe en
# yt-dlp 2026.x) ANTES de gastar una request de red: yt-dlp solo emite un
# warning ("Skipping unsupported client") y cae a los clientes por defecto.
_SUPPORTED_CLIENTS: Optional[Set[str]] = None


def get_supported_player_clients() -> Optional[Set[str]]:
    """Devuelve los nombres de player_client soportados por la version de yt-dlp instalada.

    Devuelve None si no se puede determinar (import fallido), en cuyo caso no se
    filtra nada y se comporta como antes.
    """
    global _SUPPORTED_CLIENTS
    if _SUPPORTED_CLIENTS is None:
        try:
            from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
            _SUPPORTED_CLIENTS = {c for c in INNERTUBE_CLIENTS if not c.startswith("_")}
        except Exception:  # noqa: BLE001 - degradacion segura: no filtrar
            logger.debug("No se pudo obtener la lista de player_client de yt-dlp; no se filtrara.")
            return None
    return _SUPPORTED_CLIENTS or None






class BasePlatformAdapter(IPlatformAdapter):
    """Adaptador base de infraestructura que aísla yt-dlp detrás del contrato IPlatformAdapter.

    Usa estrategias de player_client ordenadas por confiabilidad para obtener la lista completa de formatos
    (DASH video-only, audio-only, progresivos) sin provocar 403 ni limitar resoluciones.
    Soporta cookies de navegador y archivos cookies.txt personalizados para contenido con restricción de edad.
    """

    CLIENT_STRATEGIES: List[Optional[List[str]]] = [
        None,           # defaults de yt-dlp (agrega varios clientes internamente)
        ["tv"],         # cliente TV: suele sortear el bot-check con DASH completo
        ["tv_simply"],  # cliente TV "simply": equivalente moderno de tv_embedded
        ["android"],    # cliente Android: contenido real aunque limitado (sin PO token)
        ["ios"],        # cliente iOS: segunda via con DASH y sin PO token
        ["web"],        # cliente web clasico
        ["mweb"],       # cliente web movil
    ]
    # Clientes que SOLO se activan si el usuario aporta un PO token valido.
    # Sin PO token, "tv"/"web" devuelven storyboards (ver test_platform_adapter_formats.py).
    PO_TOKEN_CLIENTS: Set[str] = {"tv", "web"}

    def __init__(
        self,
        cookies_from_browser: Optional[str] = None,
        cookiefile: Optional[str] = None,
        po_token: Optional[str] = None,
        visitor_data: Optional[str] = None,
    ) -> None:
        self.cookies_from_browser: Optional[str] = (
            cookies_from_browser.strip() if cookies_from_browser and cookies_from_browser.strip() else None
        )
        self.cookiefile: Optional[str] = (
            cookiefile.strip() if cookiefile and cookiefile.strip() else None
        )
        self.po_token: Optional[str] = po_token.strip() if po_token and po_token.strip() else None
        self.visitor_data: Optional[str] = visitor_data.strip() if visitor_data and visitor_data.strip() else None

    def detect(self, url: Url) -> bool:
        """Determina si este adaptador puede procesar la URL (sobrescrito por adaptadores específicos)."""
        return False

    def analyze(self, url: Url) -> MediaMetadata:
        """Analiza la URL y extrae los metadatos (sobrescrito por adaptadores específicos o usado por genérico)."""
        info = self._extract_with_ytdlp(url)
        return self._parse_ytdlp_info(url, info, platform_name=url.detect_platform())

    def set_cookie_file(self, cookiefile: Optional[str]) -> None:
        """Actualiza la ruta del archivo de cookies (cookies.txt)."""
        self.cookiefile = cookiefile.strip() if cookiefile and cookiefile.strip() else None

    def set_cookies_from_browser(self, browser: Optional[str]) -> None:
        """Actualiza el navegador de cookies global (firefox/chrome/edge/...)."""
        self.cookies_from_browser = browser.strip() if browser and browser.strip() else None

    @staticmethod
    def _filter_supported_clients(player_clients: List[str]) -> List[str]:
        """Descarta player_client que la version de yt-dlp instalada no soporta.

        yt-dlp NO falla ante un cliente invalido: solo avisa ("Skipping
        unsupported client") y cae a los clientes por defecto, es decir, se
        gasta una request de red para repetir la extraccion por defecto. Filtrar
        aqui evita ese desperdicio y hace visibles los nombres obsoletos.
        """
        supported = get_supported_player_clients()
        if not supported:
            return list(player_clients)
        valid = [c for c in player_clients if c in supported]
        dropped = [c for c in player_clients if c not in supported]
        if dropped:
            logger.warning(
                "player_client no soportado por yt-dlp %s, se omite: %s",
                getattr(getattr(yt_dlp, "version", None), "__version__", "?"),
                ", ".join(dropped),
            )
        return valid

    def _build_ydl_opts(
        self,
        player_clients: Optional[List[str]] = None,
        disable_browser_cookies: bool = False,
    ) -> Dict[str, Any]:
        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "extract_flat": False,
            "format": "all",
            "remote_components": ["ejs:github"],
        }
        try:
            from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
            ffmpeg_path = FFmpegProcessAdapter().get_ffmpeg_executable()
            if ffmpeg_path and os.path.exists(ffmpeg_path):
                ydl_opts["ffmpeg_location"] = ffmpeg_path
        except Exception:
            pass

        node_path = shutil.which("node")
        if not node_path:
            for candidate in [
                r"C:\Program Files\nodejs\node.exe",
                r"C:\Program Files (x86)\nodejs\node.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\node\node.exe"),
            ]:
                if os.path.exists(candidate):
                    node_path = candidate
                    break
        if node_path:
            ydl_opts["js_runtimes"] = {"node": {"path": node_path}}
        elif shutil.which("deno"):
            ydl_opts["js_runtimes"] = {"deno": {}}

        if self.cookiefile and os.path.isfile(self.cookiefile):
            ydl_opts["cookiefile"] = self.cookiefile
        elif self.cookies_from_browser and not disable_browser_cookies:
            ydl_opts["cookiesfrombrowser"] = (self.cookies_from_browser,)

        if player_clients:
            effective = self._filter_supported_clients(player_clients)
            if effective:
                ydl_opts["extractor_args"] = {"youtube": {"player_client": effective}}
        return ydl_opts

    def _extract_with_ytdlp(self, url: Url) -> Dict[str, Any]:
        """Extrae la información con la mejor estrategia de clientes disponible.

        Una estrategia solo se considera exitosa si entregó al menos un formato REAL
        de medios (no storyboard/mhtml/thumbnail). Se acepta la primera estrategia
        que entregue video real; si ninguna entrega video, se usa la mejor que haya
        entregado solo audio; si todas fallan o devuelven únicamente recursos
        auxiliares, se lanza MediaAnalysisError.
        """
        video_info: Optional[Dict[str, Any]] = None
        audio_only_info: Optional[Dict[str, Any]] = None
        direct_url_info: Optional[Dict[str, Any]] = None
        errors: List[str] = []

        plat_name = url.detect_platform()
        is_youtube = plat_name == "YouTube"
        strategies = self.CLIENT_STRATEGIES if is_youtube else [None]

        for clients in strategies:
            try:
                opts = self._build_ydl_opts(clients)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    raw_info = ydl.extract_info(url.value, download=False)
                if not raw_info or not isinstance(raw_info, dict):
                    continue
                info: Dict[str, Any] = dict(raw_info)
                if "entries" in info or info.get("_type") == "playlist":
                    raw_entries = info.get("entries")
                    if isinstance(raw_entries, list):
                        dict_entries = [e for e in raw_entries if isinstance(e, dict)]
                        if dict_entries:
                            info = dict_entries[0]
                formats: List[Dict[str, Any]] = (
                    [f for f in info.get("formats", []) if isinstance(f, dict)]
                    if isinstance(info.get("formats"), list)
                    else []
                )

                if not formats:
                    # Extracción de archivo directo (sin lista de formatos): válida.
                    if info.get("url"):
                        direct_url_info = info
                        break
                    errors.append("respuesta sin formatos")
                    continue

                real_formats = [f for f in formats if not FormatNormalizer.is_auxiliary_format(f)]
                if not real_formats:
                    errors.append("respuesta sin formatos de medios reales (solo recursos auxiliares)")
                    continue

                video_opts = FormatNormalizer.normalize_video_quality_options(formats)
                video_fmts = FormatNormalizer.normalize_video_formats(formats)
                max_height = max([v.height for v in video_opts if v.height], default=0)
                if (max_height > 0 or len(video_fmts) > 0) and video_info is None:
                    video_info = info
                    break
                if audio_only_info is None:
                    audio_only_info = info
            except Exception as ex:
                errors.append(str(ex))
                continue

        chosen = video_info if video_info is not None else (
            direct_url_info if direct_url_info is not None else audio_only_info
        )
        if chosen is not None:
            return chosen

        has_cookie_err = any(
            ("could not copy" in e.lower() and "cookie" in e.lower())
            or "dpapi" in e.lower()
            or ("could not find" in e.lower() and "cookie" in e.lower())
            for e in errors
        )

        # Si falló por bloqueo/encriptación del navegador de cookies, reintentar sin cookies del navegador
        # para no romper videos públicos si el usuario dejó Chrome/Edge seleccionado con el navegador abierto.
        if has_cookie_err and self.cookies_from_browser:
            for clients in strategies:
                try:
                    opts = self._build_ydl_opts(clients, disable_browser_cookies=True)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        raw_retry = ydl.extract_info(url.value, download=False)
                    if not raw_retry or not isinstance(raw_retry, dict):
                        continue
                    retry_info: Dict[str, Any] = dict(raw_retry)
                    if "entries" in retry_info or retry_info.get("_type") == "playlist":
                        raw_entries = retry_info.get("entries")
                        if isinstance(raw_entries, list):
                            dict_entries = [e for e in raw_entries if isinstance(e, dict)]
                            if dict_entries:
                                retry_info = dict_entries[0]
                    formats = retry_info.get("formats") or []
                    if not formats:
                        if retry_info.get("url"):
                            return retry_info
                        continue
                    real_formats = [f for f in formats if not FormatNormalizer.is_auxiliary_format(f)]
                    if real_formats:
                        retry_info["_warning_message"] = (
                            f"No se pudieron leer las cookies de '{self.cookies_from_browser}' (el navegador está abierto en Windows). "
                            "Se muestran calidades públicas. Cierra el navegador por completo o utiliza un archivo cookies.txt para desbloquear 1080p y 4K."
                        )
                        return retry_info
                except Exception:
                    continue

        raw_msg = errors[0] if errors else "Respuesta vacía"
        clean_msg = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", raw_msg)
        clean_msg = re.sub(r"ERROR:\s*", "", clean_msg).strip()

        is_age_restricted = any(term in clean_msg.lower() for term in ("confirm your age", "age-restricted", "age restricted", "restricción de edad", "inappropriate for some users")) or ("age" in clean_msg.lower() and "sign in" in clean_msg.lower())
        if has_cookie_err and self.cookies_from_browser:
            clean_msg = (
                f"No se pudieron leer las cookies de '{self.cookies_from_browser}' (el navegador está abierto o protegido por Windows). "
                "Cierra el navegador por completo o utiliza un archivo cookies.txt en la pestaña Configuración."
            )
        elif is_age_restricted:
            clean_msg = (
                f"Este video tiene restricción de edad (+18) en {plat_name}. "
                "Para descargarlo, ve a la pestaña 'Configuración' -> 'Avanzado (Sesión y Cookies)' y carga tu archivo cookies.txt o selecciona tu navegador."
            )
        elif any(term in clean_msg.lower() for term in ("sign in", "bot", "too many requests", "429")):
            clean_msg = (
                f"La plataforma ({plat_name}) ha restringido temporalmente las solicitudes "
                "o requiere verificación de cuenta para este contenido. "
                "Puedes configurar un archivo cookies.txt o tu navegador en Configuración (sección 'Avanzado (Sesión y Cookies)')."
            )
        elif all("auxiliares" in e for e in errors):
            clean_msg = (
                "La plataforma no entregó formatos descargables para este contenido "
                "(solo recursos auxiliares). Intenta de nuevo en unos minutos."
            )

        raise MediaAnalysisError(f"Fallo al analizar el contenido multimedia: {clean_msg}")

    def _parse_ytdlp_info(self, url: Url, info: Dict[str, Any], platform_name: str) -> MediaMetadata:
        title = info.get("title") or "Sin título"
        author = info.get("uploader") or info.get("channel") or info.get("uploader_id") or ""
        description = info.get("description") or ""
        duration = float(info.get("duration") or 0.0)
        thumbnail = info.get("thumbnail") or ""
        upload_date = info.get("upload_date") or ""

        raw_formats = info.get("formats") or []
        video_quality_options = FormatNormalizer.normalize_video_quality_options(raw_formats)
        video_formats = FormatNormalizer.normalize_video_formats(raw_formats)
        audio_formats = FormatNormalizer.normalize_audio_formats(raw_formats)
        formats_list = FormatNormalizer.normalize(raw_formats)
        subtitles_list = extract_subtitle_tracks(info)

        if not formats_list and info.get("url"):
            default_fmt = FormatOption(
                format_id="default",
                extension=info.get("ext") or "mp4",
                resolution="Standard"
            )
            formats_list.append(default_fmt)

        media_id = MediaId.from_string(url.value)
        warning_msg = info.get("_warning_message")
        return MediaMetadata(
            media_id=media_id,
            url=url,
            platform=platform_name,
            title=title,
            author=author,
            description=description,
            duration_seconds=duration,
            thumbnail_url=thumbnail,
            upload_date=upload_date,
            video_quality_options=video_quality_options,
            video_formats=video_formats,
            audio_formats=audio_formats,
            formats=formats_list,
            subtitles=subtitles_list,
            warning_message=warning_msg,
        )

    def analyze_playlist(self, url: Url) -> PlaylistMetadata:
        """Extrae la lista de reproducción de forma plana y rápida (extract_flat)."""
        opts = self._build_ydl_opts()
        opts["extract_flat"] = "in_playlist"
        opts["noplaylist"] = False

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url.value, download=False)
        except Exception as ex:
            raise MediaAnalysisError(f"No se pudo analizar la lista de reproducción: {ex}") from ex

        if not info or not isinstance(info, dict):
            raise MediaAnalysisError("La plataforma devolvió una lista vacía o no válida.")

        entries_raw = info.get("entries")
        entries_list = entries_raw if isinstance(entries_raw, list) else []
        entries: List[PlaylistEntry] = []
        for e in entries_list:
            if not e or not isinstance(e, dict):
                continue
            v_id = str(e.get("id") or "")
            v_title = str(e.get("title") or "Sin título")
            v_url = str(e.get("url") or e.get("webpage_url") or "")
            if not v_url and v_id:
                v_url = f"https://www.youtube.com/watch?v={v_id}"
            v_dur = float(e.get("duration") or 0.0)
            v_thumb = str(e.get("thumbnail") or "")
            v_uploader = str(e.get("uploader") or e.get("channel") or "")
            entries.append(
                PlaylistEntry(
                    video_id=v_id,
                    title=v_title,
                    url=v_url,
                    duration_seconds=v_dur,
                    thumbnail_url=v_thumb,
                    uploader=v_uploader,
                )
            )

        return PlaylistMetadata(
            playlist_id=str(info.get("id") or "playlist"),
            title=str(info.get("title") or "Lista de reproducción"),
            url=url,
            platform=url.detect_platform(),
            uploader=str(info.get("uploader") or info.get("channel") or ""),
            description=str(info.get("description") or ""),
            entries=entries,
        )

