from typing import Any, Dict, List, Optional
import yt_dlp
import re

from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.services.format_normalizer import FormatNormalizer
from src.domain.exceptions.domain_exceptions import MediaAnalysisError
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url

logger = __import__("logging").getLogger(__name__)


class BasePlatformAdapter(IPlatformAdapter):
    """Adaptador base de infraestructura que aísla yt-dlp detrás del contrato IPlatformAdapter sin cookies de navegador.

    Estrategia controlada de player clients: se prueban varias configuraciones acotadas y se conserva
    la que exponga más formatos reales (sin loops infinitos ni autenticación).
    """

    # Configuraciones probadas de forma controlada. La primera (sin override) delega en los
    # clientes por defecto de yt-dlp; las siguientes son fallbacks explícitos.
    CLIENT_STRATEGIES: List[Optional[List[str]]] = [
        None,                       # yt-dlp defaults (formato completo en el entorno actual)
        ["web", "android", "mweb"],  # estable y descargable, aunque puede estar limitado
        ["android_vr", "tv"],        # rico en flujos video-only + audio-only
    ]

    def _build_ydl_opts(self, player_clients: Optional[List[str]] = None) -> Dict[str, Any]:
        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "extract_flat": False,
            "format": "all",
        }
        if player_clients:
            ydl_opts["extractor_args"] = {"youtube": {"player_client": player_clients}}
        return ydl_opts

    def _extract_with_ytdlp(self, url: Url) -> Dict[str, Any]:
        """Extrae la información con la mejor estrategia de clientes disponible (sin cookies)."""
        results: List[Dict[str, Any]] = []
        errors: List[str] = []

        for clients in self.CLIENT_STRATEGIES:
            try:
                ydl_opts = self._build_ydl_opts(clients)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url.value, download=False)
                    if info:
                        results.append((clients, info))
                        # Si la estrategia base ya es rica (2+ resoluciones distintas),
                        # no hace falta seguir probando las demás.
                        if clients is None and self._count_distinct_heights(info) >= 2:
                            break
            except Exception as ex:
                errors.append(str(ex))

        if not results:
            raise self._build_analysis_error(errors)

        # Conservar el resultado con MÁS formatos reales (más resolución detectada)
        results.sort(key=lambda item: self._count_real_formats(item[1]), reverse=True)
        _, info = results[0]

        if "entries" in info or info.get("_type") == "playlist":
            entries = [e for e in info.get("entries", []) if e]
            if entries:
                return entries[0]
        return info

    @staticmethod
    def _count_real_formats(info: Dict[str, Any]) -> int:
        count = 0
        for f in info.get("formats", []):
            if FormatNormalizer.is_auxiliary_format(f):
                continue
            vcodec = str(f.get("vcodec") or "none")
            acodec = str(f.get("acodec") or "none")
            if vcodec != "none" or acodec != "none":
                count += 1
        return count

    @staticmethod
    def _count_distinct_heights(info: Dict[str, Any]) -> int:
        heights = set()
        for f in info.get("formats", []):
            if FormatNormalizer.is_auxiliary_format(f):
                continue
            h = f.get("height")
            if h:
                heights.add(h)
        return len(heights)

    def _build_analysis_error(self, errors: List[str]) -> MediaAnalysisError:
        combined = " | ".join(e for e in errors if e)
        raw_msg = combined or "Error desconocido al extraer la información."
        clean_msg = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", raw_msg)
        clean_msg = re.sub(r"ERROR:\s*", "", clean_msg).strip()

        if any(term in clean_msg.lower() for term in ("sign in", "confirm you're not a bot", "not a bot", "too many requests", "429", "forbidden", "please sign in")):
            clean_msg = (
                "La plataforma (YouTube) ha restringido temporalmente las solicitudes o "
                "requiere verificación de inicio de sesión para este contenido. "
                "Inténtalo de nuevo más tarde o usa una URL pública."
            )

        return MediaAnalysisError(f"Fallo al analizar el contenido multimedia: {clean_msg[:500]}")

    def _parse_ytdlp_info(self, url: Url, info: Dict[str, Any], platform_name: str) -> MediaMetadata:
        title = info.get("title") or "Sin título"
        author = info.get("uploader") or info.get("channel") or info.get("uploader_id") or ""
        duration = float(info.get("duration") or 0.0)
        thumbnail = info.get("thumbnail") or ""
        upload_date = info.get("upload_date") or ""

        raw_formats = info.get("formats") or []
        video_quality_options = FormatNormalizer.normalize_video_quality_options(raw_formats)
        video_formats = FormatNormalizer.normalize_video_formats(raw_formats)
        audio_formats = FormatNormalizer.normalize_audio_formats(raw_formats)
        formats_list = FormatNormalizer.normalize(raw_formats)

        # Si no se extrajeron formatos individuales pero hay URL directa
        if not formats_list and info.get("url"):
            default_fmt = FormatOption(
                format_id="default",
                extension=info.get("ext") or "mp4",
                resolution="Standard"
            )
            formats_list.append(default_fmt)

        media_id = MediaId.from_string(url.value)
        return MediaMetadata(
            media_id=media_id,
            url=url,
            platform=platform_name,
            title=title,
            author=author,
            duration_seconds=duration,
            thumbnail_url=thumbnail,
            upload_date=upload_date,
            video_quality_options=video_quality_options,
            video_formats=video_formats,
            audio_formats=audio_formats,
            formats=formats_list
        )
