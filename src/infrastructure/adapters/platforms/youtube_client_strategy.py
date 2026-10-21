"""Politica compartida de clientes de YouTube para yt-dlp.

Centraliza el fallback NATIVO de yt-dlp (``player_client``) y los saltos del
extractor (``player_skip``) para que el analisis y la descarga usen exactamente
la misma configuracion: si el analisis prometio 4K, la descarga debe poder
bajarlo con los mismos clientes.

Contexto del problema
---------------------
En visitas anonimas YouTube degrada la respuesta: el cliente ``web`` exige un
PO token (GVS) para las calidades altas y, sin el, entrega como maximo 360p
mas storyboards. yt-dlp resuelve esto con su mecanismo de fallback nativo:
``player_client`` acepta una LISTA de clientes que se prueban en orden dentro
de una MISMA extraccion y cuyos formatos se fusionan.

``player_skip`` evita las peticiones que devuelven la via degradada:

- ``webpage``: no descarga la pagina inicial (la que triggers el bot-check /
  age-gate que produce la degradacion a 360p).
- ``configs``: no descarga el ``ytcfg`` de cada cliente no-web. Es una request
  menos por cliente de fallback => menos riesgo de HTTP 429.

Los saltos SOLO se aplican en la via anonima: con cookies la pagina inicial si
aporta el ``player_response`` y el ``visitor_data`` de mayor calidad, asi que
saltarla solo empeoraria el resultado.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Set

logger = logging.getLogger(__name__)

#: Namespace de extractor_args reservado a YouTube.
YOUTUBE_NAMESPACE = "youtube"

#: Clientes que yt-dlp renombro o retiro.
#:
#: ``tv_embedded`` (TVHTML5EMBEDDEDPLAYER) ya NO existe en yt-dlp 2026.x. El
#: cliente de TV embebido vigente que ademas NO exige PO token (requisito para
#: superar el tope de 360p en visita anonima) es ``tv_downgraded``
#: (TVHTML5 con version degradada). ``tv_simply`` (TVHTML5_SIMPLY) tambien es
#: de la familia TV, pero exige PO token para DASH/HTTPS, por lo que sus
#: formatos se descartan si el usuario no aporta un token.
#:
#: Sin esta tabla, yt-dlp solo emitiria un warning ("Skipping unsupported
#: client") y gastaria una request de red para repetir la extraccion por
#: defecto.
LEGACY_CLIENT_ALIASES: Dict[str, str] = {
    "tv_embedded": "tv_downgraded",
}

#: Fallback NATIVO de yt-dlp: una sola extraccion en la que yt-dlp prueba cada
#: cliente en el orden dado y fusiona sus formatos.
#:
#: El orden importa: yt-dlp procesa la lista en orden (ver
#: ``yt_dlp/extractor/youtube/_video.py::_extract_player_responses``, que la
#: invierte y extrae con ``pop()``), de modo que el PRIMERO se intenta
#: primero.
#:
#: La seleccion se basa en la politica GVS de cada cliente (yt-dlp 2026.08.19):
#:
#: ============ ========== ======= ====== =====
#: cliente       cookies     HTTPS   DASH   HLS
#: ============ ========== ======= ====== =====
#: ios           no          REQ     no     REQ
#: tv_downgraded si          no      no     no
#: tv_simply     no          REQ     REQ     rec
#: web           si          REQ     REQ     rec
#: ============ ========== ======= ====== =====
#:
#: ``ios`` aporta DASH (video-only de alta resolucion) sin PO token.
#: ``tv_downgraded`` es el cliente de TV embebido: no exige PO token en NINGUN
#: protocolo, asi que entrega el ladder DASH completo en visita anonima.
#: ``tv_simply`` rinde al maximo cuando el usuario aporta un PO token.
#: ``web`` queda como cierre: es el cliente mas restringido en anonimo.
NATIVE_FALLBACK_CLIENTS: List[str] = ["ios", "tv_downgraded", "tv_simply", "web"]

#: Saltos del extractor de YouTube aceptados por yt-dlp 2026.x:
#:
#: - ``webpage``: no descarga la pagina inicial.
#: - ``configs``: no descarga el ``ytcfg`` de los clientes no-web.
#: - ``js``: no descarga el player JS (incompatible con REQUIRE_JS_PLAYER).
#: - ``initial_data``: no extrae el initial data de la pagina.
#:
#: Un valor desconocido se ignora en silencio, asi que la lista se filtra
#: contra este conjunto para no propagar errores tipograficos.
VALID_PLAYER_SKIP: Set[str] = {"webpage", "configs", "js", "initial_data"}

#: Saltos aplicados por defecto en la via anonima.
DEFAULT_PLAYER_SKIP: List[str] = ["webpage", "configs"]

# Cache perezoso de los player_client soportados por la version de yt-dlp
# instalada. Permite descartar nombres obsoletos ANTES de gastar una request
# de red.
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


def resolve_player_clients(clients: Optional[Sequence[str]]) -> List[str]:
    """Normaliza una lista de player_client: alias historicos + filtro de soportados.

    - ``tv_embedded`` se traduce a ``tv_simply`` (su equivalente vigente).
    - Los clientes que la version de yt-dlp instalada no soporta se descartan.
      yt-dlp NO falla ante un cliente invalido: solo avisa ("Skipping
      unsupported client") y cae a los clientes por defecto, es decir, se
      gasta una request de red para repetir la extraccion por defecto.
    - Se conservan duplicados evitados y el orden original (el orden es el
      orden de intento de yt-dlp).
    """
    if not clients:
        return []

    resolved: List[str] = []
    for client in clients:
        name = (client or "").strip().lower()
        if not name:
            continue
        alias = LEGACY_CLIENT_ALIASES.get(name)
        if alias:
            logger.info(
                "player_client obsoleto '%s': se usa su equivalente vigente '%s'.",
                name,
                alias,
            )
            name = alias
        if name not in resolved:
            resolved.append(name)

    supported = get_supported_player_clients()
    if not supported:
        return resolved

    valid = [c for c in resolved if c in supported]
    dropped = [c for c in resolved if c not in supported]
    if dropped:
        logger.warning(
            "player_client no soportado por la version de yt-dlp instalada, se omite: %s",
            ", ".join(dropped),
        )
    return valid


def sanitize_player_skip(player_skip: Optional[Sequence[str]]) -> List[str]:
    """Filtra los saltos del extractor contra los valores que yt-dlp reconoce."""
    if not player_skip:
        return []
    valid: List[str] = []
    for item in player_skip:
        name = (item or "").strip().lower()
        if not name or name in valid:
            continue
        if name not in VALID_PLAYER_SKIP:
            logger.warning("player_skip no reconocido por yt-dlp, se omite: %s", name)
            continue
        valid.append(name)
    return valid


def build_youtube_extractor_args(
    clients: Optional[Sequence[str]] = None,
    player_skip: Optional[Sequence[str]] = None,
    anonymous: bool = True,
) -> Dict[str, Any]:
    """Construye el bloque ``extractor_args['youtube']`` que consume yt-dlp.

    Args:
        clients: lista de player_client a usar (fallback nativo). Si es None o
            queda vacia tras el filtrado, yt-dlp usa sus clientes por defecto.
        player_skip: saltos del extractor. ``None`` usa ``DEFAULT_PLAYER_SKIP``.
        anonymous: True en la via sin cookies. Los saltos del extractor solo se
            aplican en esa via: con cookies la pagina inicial aporta el
            player_response y el visitor_data de mayor calidad.
    """
    args: Dict[str, Any] = {}

    effective = resolve_player_clients(clients)
    if effective:
        args["player_client"] = effective

    if anonymous:
        skip = sanitize_player_skip(
            DEFAULT_PLAYER_SKIP if player_skip is None else player_skip
        )
        if skip:
            args["player_skip"] = skip

    return args
