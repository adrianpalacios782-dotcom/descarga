"""Sanitización y extracción limpia de URLs.

1. `sanitize_single_video_url`: Elimina parámetros de lista de reproducción
   (`?list=...`, `index`, `start_radio`) de enlaces a videos individuales.
2. `extract_clean_url`: Extrae una URL válida de medios desde un texto arbitrario
   o portapapeles, descartando texto envolvente, corchetes, comillas y signos de
   puntuación final.
"""
import re
from typing import List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Parámetros que referencian contexto de playlist/radio en URLs de video.
_PLAYLIST_CONTEXT_PARAMS = frozenset({"list", "index", "start_radio", "pp"})

# Rutas que SON una playlist (el parámetro list es la intención del usuario).
_PLAYLIST_PATH_MARKERS = ("/playlist", "/channel/", "/c/", "/user/", "/@")
_WATCH_PATH_MARKERS = ("/watch", "/shorts/", "/embed/", "/live/")

# Signos de puntuación y delimitadores que suelen quedar pegados al final de una URL.
_TRAILING_PUNCTUATION = ".,;:!?)]}\u00ab\u00bb\u201d\u201c\u2026'\""
_LEADING_DELIMITERS = "([<{«\"'"

# Regex para detectar URLs completas (con o sin esquema explícito)
_MEDIA_URL_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:'
    r'youtube\.com|youtu\.be|'
    r'instagram\.com|instagr\.am|'
    r'facebook\.com|fb\.watch|'
    r'tiktok\.com|vm\.tiktok\.com|'
    r'twitch\.tv|'
    r'kick\.com|'
    r'vimeo\.com|'
    r'twitter\.com|x\.com|'
    r'reddit\.com|'
    r'soundcloud\.com|'
    r'pinterest\.com|pin\.it|'
    r'dailymotion\.com|dai\.ly|'
    r'bilibili\.com|'
    r'bsky\.app|'
    r'threads\.net'
    r')[^\s<>"\']*',
    re.IGNORECASE,
)

_GENERIC_HTTP_URL_REGEX = re.compile(
    r'https?://[^\s<>"\']+',
    re.IGNORECASE,
)


def extract_clean_url(text: Optional[str]) -> Optional[str]:
    """Extrae una URL limpia desde un texto o portapapeles.

    - Busca primero plataformas conocidas o cualquier URL http/https.
    - Elimina delimitadores iniciales y signos de puntuación final adheridos.
    - Si la URL carece de esquema pero coincide con un host conocido, antepone 'https://'.
    - Aplica sanitización de parámetros de playlist para videos individuales.
    - Retorna None si no hay ninguna URL válida.
    """
    if not text or not isinstance(text, str):
        return None

    raw = text.strip()
    if not raw:
        return None

    match = _MEDIA_URL_REGEX.search(raw)
    if not match:
        match = _GENERIC_HTTP_URL_REGEX.search(raw)
    if not match:
        return None

    candidate = match.group(0)
    candidate = candidate.lstrip(_LEADING_DELIMITERS)
    candidate = candidate.rstrip(_TRAILING_PUNCTUATION)

    if not candidate:
        return None

    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    try:
        parsed = urlparse(candidate)
        if not parsed.netloc:
            return None
    except Exception:
        return None

    return sanitize_single_video_url(candidate)


def sanitize_single_video_url(url: str) -> str:
    """Devuelve `url` sin parámetros de contexto de playlist.

    - Conserva esquema, host, ruta y demás query params (ej. `v`, `t`, `si`).
    - No altera URLs de playlist explícitas ni URLs sin query.
    - Ante cualquier error de parseo retorna la URL original intacta.
    """
    if not url:
        return url

    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url

    if not parsed.query:
        return url

    path_lower = parsed.path.lower()
    host_lower = parsed.netloc.lower()
    if host_lower.startswith("www."):
        host_lower = host_lower[4:]

    is_playlist_page = any(m in path_lower for m in _PLAYLIST_PATH_MARKERS)
    # Página de video: /watch, /shorts, /embed, /live o el formato corto youtu.be/<id>.
    is_video_page = (
        host_lower == "youtu.be"
        or any(m in path_lower for m in _WATCH_PATH_MARKERS)
    )
    if is_playlist_page or not is_video_page:
        return url

    kept: List[Tuple[str, str]] = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _PLAYLIST_CONTEXT_PARAMS
    ]
    if len(kept) == len(parse_qsl(parsed.query, keep_blank_values=True)):
        return url  # no había parámetros de playlist: URL intacta

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(kept),
            parsed.fragment,
        )
    )

