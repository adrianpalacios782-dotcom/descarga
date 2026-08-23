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

    Usa estrategias de player_client ordenadas por confiabilidad para obtener la lista completa de formatos
    (DASH video-only, audio-only, progresivos) sin provocar 403 ni limitar resoluciones.

    IMPORTANTE: cuando YouTube aplica su verificación anti-bot a un cliente, NO siempre
    falla la extracción: puede responder "exitosamente" con metadata completa (título,
    miniatura, canal...) pero SOLO formatos storyboard (mhtml sb0-sb3). Ese resultado es
    degenerado y NO debe aceptarse como análisis válido si otra estrategia entrega
    formatos reales.
    """

    CLIENT_STRATEGIES: List[Optional[List[str]]] = [
        None,        # defaults de yt-dlp (agrega varios clientes internamente)
        ["tv"],      # cliente TV: suele sortear el bot-check con DASH completo
        ["android"], # cliente Android: contenido real aunque limitado (sin PO token)
        ["web"],     # cliente web clásico
        ["mweb"],    # cliente web móvil
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
                max_height = max([v.height for v in video_opts], default=0)
                if max_height > 0 and video_info is None:
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

        raw_msg = errors[0] if errors else "Respuesta vacía"
        clean_msg = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", raw_msg)
        clean_msg = re.sub(r"ERROR:\s*", "", clean_msg).strip()

        if any(term in clean_msg.lower() for term in ("sign in", "bot", "too many requests", "429")):
            clean_msg = (
                "La plataforma (YouTube) ha restringido temporalmente las solicitudes "
                "o requiere verificación para este contenido."
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
            description=description,
            duration_seconds=duration,
            thumbnail_url=thumbnail,
            upload_date=upload_date,
            video_quality_options=video_quality_options,
            video_formats=video_formats,
            audio_formats=audio_formats,
            formats=formats_list
        )
