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

Evidencia medida (yt-dlp 2026.08.19, video "TR3Vdo5etCQ", IP sin sesion)
----------------------------------------------------------------------
=============================== ============================ ==================
configuracion                   ladder de alturas           resultado
=============================== ============================ ==================
``web_embedded``                144 240 360 480 720 1080    4K + 4 audios
                                1440 2160                   separados
``web_embedded`` + skip configs ERROR 152                  se pierde todo
``web_embedded`` + skip webpage 144 ... 2160                equivalente
``android ios web_creator web`` 360                         solo 360p
=============================== ============================ ==================

De ahi se derivan las dos decisiones de este modulo:

1. ``web_embedded`` (WEB_EMBEDDED_PLAYER) es el cliente que rompe el tope de
   360p: NO exige PO token en NINGUN protocolo, a diferencia de ``web``,
   ``android`` y ``web_creator``. Por eso va el PRIMERO en la lista.
2. NO se salta nada del extractor. Saltar ``configs`` destruye el ladder
   (error 152: YouTube rechaza el contexto de embed) y saltar ``webpage``
   elimina el ``visitor_data`` que necesitan los clientes autenticados. El
   salto se mantiene como capacidad configurable, pero por defecto es VACIO:
   el ahorro de una request no compensa perder 4K.

La lista de clientes cambia segun haya sesion o no: ``web_creator`` exige
autenticacion (``REQUIRE_AUTH``), asi que solo es utilizable con cookies.
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
#: ============ ========== ======= ====== ===== ==============
#: cliente       cookies     HTTPS   DASH   HLS   requiere
#:                                            sesion
#: ============ ========== ======= ====== ===== ==============
#: web_embedded  si          no      no     no    no
#: ios           no          REQ     no     REQ   no
#: android       no          REQ     REQ    REQ   no
#: web           si          REQ     REQ    rec   no
#: web_creator   si          REQ     REQ    rec   SI
#: ============ ========== ======= ====== ===== ==============
#:
#: ``web_embedded`` va el primero porque es el unico que entrega el ladder
#: completo (hasta 2160p) SIN PO token y SIN sesion: es el cliente que rompe
#: el tope de 360p en visita anonima.
#: ``ios`` aporta DASH (video-only de alta resolucion) sin PO token.
#: ``android`` y ``web`` cierran la lista: exigen PO token, pero si el usuario
#: aporta uno o tiene cuenta Premium sus formatos no se descartan.
ANONYMOUS_FALLBACK_CLIENTS: List[str] = ["web_embedded", "ios", "android", "web"]

#: Lista de clientes cuando hay SESION (cookies del navegador o cookies.txt).
#:
#: Anade ``web_creator`` (WEB_CREATOR), que en yt-dlp 2026.x tiene
#: ``REQUIRE_AUTH: True`` ("este cliente ahora exige iniciar sesion para cada
#: video"): es el unico cliente de la lista que solo existe si hay sesion, y el
#: que aporta las calidades de cuenta (Premium, contenido para miembros).
AUTHENTICATED_FALLBACK_CLIENTS: List[str] = [
    "web_embedded",
    "ios",
    "android",
    "web",
    "web_creator",
]

#: Alias historico: la lista de clientes del fallback nativo en via anonima.
NATIVE_FALLBACK_CLIENTS: List[str] = ANONYMOUS_FALLBACK_CLIENTS


def get_fallback_clients(authenticated: bool) -> List[str]:
    """Devuelve la lista de player_client segun haya sesion o no.

    Args:
        authenticated: True si la extraccion lleva cookies (sesion del navegador
            o cookies.txt), False en la via anonima.

    Returns:
        Una copia de la lista correspondiente, para que el llamante pueda
        modificarla sin alterar la politica global.
    """
    if authenticated:
        return list(AUTHENTICATED_FALLBACK_CLIENTS)
    return list(ANONYMOUS_FALLBACK_CLIENTS)

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

#: Saltos aplicados por defecto: NINGUNO.
#:
#: Medido (yt-dlp 2026.08.19, video "TR3Vdo5etCQ"):
#:
#: - con ``["configs"]`` el cliente ``web_embedded`` falla con "Error code: 152"
#:   (YouTube rechaza el contexto de embed) y el ladder cae a ``[360]``.
#: - con ``["webpage"]`` el ladder se mantiene, pero se pierde el
#:   ``visitor_data`` que necesitan los clientes autenticados para resolver el
#:   PO token.
#:
#: Ahorrar una request por cliente no compensa perder el ladder completo, asi
#: que el salto queda disponible pero desactivado. El modulo mantiene la
#: capacidad de activarlo (``player_skip`` explicito) por si el usuario
#: necesita minimizar el trafico.
DEFAULT_PLAYER_SKIP: List[str] = []

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
) -> Dict[str, Any]:
    """Construye el bloque ``extractor_args['youtube']`` que consume yt-dlp.

    Args:
        clients: lista de player_client a usar (fallback nativo). Si es None o
            queda vacia tras el filtrado, yt-dlp usa sus clientes por defecto.
        player_skip: saltos del extractor. ``None`` usa ``DEFAULT_PLAYER_SKIP``
            (vacio: no se salta nada, ver la nota de evidencia del modulo).

    La politica ya NO distingue la via anonima de la autenticada: con la
    evidencia medida, saltarse la pagina inicial o el ``ytcfg`` degrada el
    ladder en ambos casos.
    """
    args: Dict[str, Any] = {}

    effective = resolve_player_clients(clients)
    if effective:
        args["player_client"] = effective

    skip = sanitize_player_skip(
        DEFAULT_PLAYER_SKIP if player_skip is None else player_skip
    )
    if skip:
        args["player_skip"] = skip

    return args
