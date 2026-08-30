import logging
import re
import time
from typing import Any, Dict, List, Optional, cast

import yt_dlp

from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import MediaAnalysisError
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter

logger = logging.getLogger(__name__)


class TikTokAdapter(BasePlatformAdapter):
    """Adaptador de infraestructura específico para extraer contenido de TikTok.

    TikTok NO necesita estrategias de player_client múltiples como YouTube.
    Usa extracción única con curl_cffi (impersonation) que yt-dlp aplica
    automáticamente cuando curl_cffi está instalado.

    El strategy loop del base adapter causa rate-limiting en TikTok porque
    crea múltiples instancias yt-dlp, cada una haciendo requests separados
    al servidor de TikTok. Aquí hacemos un solo intento con retry manual.
    """

    MAX_RETRIES = 3
    RETRY_DELAYS = [2.0, 5.0, 10.0]

    def detect(self, url: Url) -> bool:
        return url.detect_platform() == "TikTok"

    def analyze(self, url: Url) -> MediaMetadata:
        info = self._extract_tiktok(url)
        return self._parse_ytdlp_info(url, info, platform_name="TikTok")

    def _extract_tiktok(self, url: Url) -> Dict[str, Any]:
        """Extrae información de TikTok con retry y backoff.

        Usa una única instancia yt-dlp por intento (sin strategy loop)
        para evitar rate-limiting por requests múltiples.
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            if attempt > 0:
                delay = self.RETRY_DELAYS[min(attempt - 1, len(self.RETRY_DELAYS) - 1)]
                logger.info(f"TikTok: reintento {attempt + 1}/{self.MAX_RETRIES} tras {delay}s")
                time.sleep(delay)

            try:
                opts = self._build_ydl_opts()
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url.value, download=False)
                    if not info:
                        last_error = "Respuesta vacía de TikTok"
                        continue
                    if "entries" in info or info.get("_type") == "playlist":
                        entries = [e for e in info.get("entries", []) if e]
                        if entries:
                            info = entries[0]
                    formats = info.get("formats") or []
                    if not formats:
                        last_error = "TikTok devolvió 0 formatos disponibles"
                        continue
                    return cast(Dict[str, Any], info)
            except Exception as ex:
                last_error = str(ex)
                logger.warning(f"TikTok: intento {attempt + 1} falló: {ex}")
                continue

        clean_msg = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", last_error or "Respuesta vacía")
        clean_msg = re.sub(r"ERROR:\s*", "", clean_msg).strip()
        clean_msg = re.sub(r"please report this issue on.*", "", clean_msg).strip()

        if any(term in clean_msg.lower() for term in ("sign in", "bot", "too many requests", "429")):
            clean_msg = (
                "TikTok ha restringido temporalmente las solicitudes. "
                "Intenta de nuevo en unos minutos."
            )

        raise MediaAnalysisError(
            f"TikTok no pudo extraer los datos del video: {clean_msg}"
        )

    def _build_ydl_opts(self, player_clients: Optional[List[str]] = None) -> Dict[str, Any]:
        """Opciones mínimas para TikTok — sin extractor_args, sin player_client."""
        return {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "format": "all",
        }
