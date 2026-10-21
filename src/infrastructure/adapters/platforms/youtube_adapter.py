from typing import Any, Dict, List, Optional

from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter
from src.infrastructure.adapters.platforms.youtube_client_strategy import (
    NATIVE_FALLBACK_CLIENTS,
    YOUTUBE_NAMESPACE,
    build_youtube_extractor_args,
)


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
        """Opciones de yt-dlp + la política completa de YouTube.

        Reúne tres cosas en el bloque ``extractor_args['youtube']``:

        1. ``player_client``: fallback NATIVO de yt-dlp. Una lista de clientes
           que yt-dlp prueba EN ORDEN dentro de una sola extracción y cuyos
           formatos fusiona. Sin esta lista, yt-dlp usa sus defaults
           (``visionos`` + ``web``), que exigen PO token y devuelven como
           máximo 360p en visita anónima.
        2. ``player_skip``: en la vía anónima se saltan la página inicial y el
           ``ytcfg`` por cliente, que son las peticiones que devuelven la
           respuesta degradada. Con cookies NO se saltan: la página aporta el
           ``player_response`` y el ``visitor_data`` de mayor calidad.
        3. ``po_token`` / ``visitor_data``: credenciales de sesión de YouTube.
           Sin ellos los clientes "web"/"tv" responden con storyboards en vez
           de DASH completo. Se inyectan como extractor_args, que es donde
           yt-dlp las lee (ver yt_dlp/extractor/youtube/_video.py::_get_config_po_token).
        """
        ydl_opts = super()._build_ydl_opts(player_clients, disable_browser_cookies)

        extractor_args = dict(ydl_opts.get("extractor_args") or {})
        youtube_args = dict(extractor_args.get(YOUTUBE_NAMESPACE) or {})

        anonymous = not ("cookiefile" in ydl_opts or "cookiesfrombrowser" in ydl_opts)
        youtube_args.update(build_youtube_extractor_args(player_clients, anonymous=anonymous))

        if self.po_token:
            youtube_args["po_token"] = self._po_token_entries(player_clients)
        if self.visitor_data:
            youtube_args["visitor_data"] = self.visitor_data

        if youtube_args:
            extractor_args[YOUTUBE_NAMESPACE] = youtube_args
            ydl_opts["extractor_args"] = extractor_args
        else:
            ydl_opts.pop("extractor_args", None)
        return ydl_opts

    def _po_token_entries(self, player_clients: Optional[List[str]]) -> List[str]:
        """Normaliza el PO token al formato que espera yt-dlp: "CLIENT.CONTEXT+TOKEN".

        - Si el valor ya viene en ese formato ("web.gvs+AAAA") se pasa tal cual.
        - Si es un token "crudo" (base64url sin prefijo) se aplica a todos los
          clientes de la estrategia actual con contexto GVS.

        Cuando la estrategia usa los defaults de yt-dlp (visionos + web) se
        cubren tambien esos clientes: el token se indexa por nombre de cliente,
        asi que las entradas que no apliquen se ignoran solas.
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
            clients = list(NATIVE_FALLBACK_CLIENTS) + ["visionos"]
        seen: List[str] = []
        for client in clients:
            if client not in seen:
                seen.append(client)
        return [f"{client}.gvs+{raw}" for client in seen]
