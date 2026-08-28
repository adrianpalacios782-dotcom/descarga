"""Sanitización de URLs con parámetros de playlist.

Al pegar o analizar un enlace de video individual, YouTube suele incluir
parámetros de lista de reproducción (`?list=...`, `&list=...`, `index`,
`start_radio`). Para el flujo de descarga única interesa SOLO el video:
estos parámetros se eliminan para que la plataforma resuelva exactamente
el recurso visualizado y yt-dlp no intente expandir la lista.

Las URLs de playlist explícitas (`/playlist?list=...`) NO se tocan: ahí el
usuario pidió la lista completa.
"""
from typing import List, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Parámetros que referencian contexto de playlist/radio en URLs de video.
_PLAYLIST_CONTEXT_PARAMS = frozenset({"list", "index", "start_radio", "pp"})

# Rutas que SON una playlist (el parámetro list es la intención del usuario).
_PLAYLIST_PATH_MARKERS = ("/playlist", "/channel/", "/c/", "/user/", "/@")
_WATCH_PATH_MARKERS = ("/watch", "/shorts/", "/embed/", "/live/")


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
