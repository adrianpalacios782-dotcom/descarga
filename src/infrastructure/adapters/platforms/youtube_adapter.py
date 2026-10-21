from typing import Any, Dict, List, Optional

from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter


class YouTubeAdapter(BasePlatformAdapter):
    """Adaptador de infraestructura específico para extraer contenido de YouTube."""

    def detect(self, url: Url) -> bool:
        return url.detect_platform() == "YouTube"

    def analyze(self, url: Url) -> MediaMetadata:
        info = self._extract_with_ytdlp(url)
        return self._parse_ytdlp_info(url, info, platform_name="YouTube")

    def _build_ydl_opts(
        self,
        player_clients: Optional[List[str]] = None,
        disable_browser_cookies: bool = False,
    ) -> Dict[str, Any]:
        """Opciones de yt-dlp + las que solo aplican a YouTube (PO token / visitor_data).

        El PO token y el visitor_data son credenciales de sesion de YouTube: sin
        ellos los clientes "web"/"tv" responden con storyboards en vez de DASH
        completo. Se inyectan como extractor_args, que es donde yt-dlp las lee
        (ver yt_dlp/extractor/youtube/_video.py::_get_config_po_token).
        """
        ydl_opts = super()._build_ydl_opts(player_clients, disable_browser_cookies)
        youtube_args = ydl_opts.setdefault("extractor_args", {}).setdefault("youtube", {})

        if self.po_token:
            youtube_args["po_token"] = self._po_token_entries(player_clients)
        if self.visitor_data:
            youtube_args["visitor_data"] = self.visitor_data

        if not youtube_args:
            ydl_opts.pop("extractor_args", None)
        return ydl_opts

    def _po_token_entries(self, player_clients: Optional[List[str]]) -> List[str]:
        """Normaliza el PO token al formato que espera yt-dlp: "CLIENT.CONTEXT+TOKEN".

        - Si el valor ya viene en ese formato ("web.gvs+AAAA") se pasa tal cual.
        - Si es un token "crudo" (base64url sin prefijo) se aplica a todos los
          clientes de la estrategia actual con contexto GVS.
        """
        raw = (self.po_token or "").strip()
        if not raw:
            return []
        if "+" in raw:
            # base64url no usa "+" (usa "-"), asi que el "+" solo puede ser el
            # separador "CLIENT.CONTEXT+TOKEN" de yt-dlp.
            return [raw]
        clients = [c for c in (player_clients or []) if c]
        if not clients:
            clients = ["web"]
        return [f"{client}.gvs+{raw}" for client in clients]
