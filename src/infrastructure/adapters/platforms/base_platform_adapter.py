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


class BasePlatformAdapter(IPlatformAdapter):
    """Adaptador base de infraestructura que aísla yt-dlp detrás del contrato IPlatformAdapter sin cookies de navegador.

    Usa restricciones mínimas de player_client para obtener la lista completa de formatos
    (DASH video-only, audio-only, progresivos) sin provocar 403 ni limitar resoluciones.
    """

    CLIENT_STRATEGIES: List[Optional[List[str]]] = [
        None,
        ["web"],
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
        """Extrae la información con la mejor estrategia de clientes disponible."""
        results: List[Dict[str, Any]] = []
        errors: List[str] = []

        for clients in self.CLIENT_STRATEGIES:
            try:
                opts = self._build_ydl_opts(clients)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url.value, download=False)
                    if not info:
                        continue
                    if "entries" in info or info.get("_type") == "playlist":
                        entries = [e for e in info.get("entries", []) if e]
                        if entries:
                            info = entries[0]
                    formats = info.get("formats") or []
                    video_opts = FormatNormalizer.normalize_video_quality_options(formats)
                    max_height = max([v.height for v in video_opts], default=0)
                    results.append((max_height, len(formats), info))
            except Exception as ex:
                errors.append(str(ex))
                continue

        if results:
            results.sort(key=lambda r: (r[0], r[1]), reverse=True)
            return results[0][2]

        raw_msg = errors[0] if errors else "Respuesta vacía"
        clean_msg = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", raw_msg)
        clean_msg = re.sub(r"ERROR:\s*", "", clean_msg).strip()

        if any(term in clean_msg.lower() for term in ("sign in", "bot", "too many requests", "429")):
            clean_msg = (
                "La plataforma (YouTube) ha restringido temporalmente las solicitudes "
                "o requiere verificación para este contenido."
            )

        raise MediaAnalysisError(f"Fallo al analizar el contenido multimedia: {clean_msg}")

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
