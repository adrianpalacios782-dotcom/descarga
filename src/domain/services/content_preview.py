"""Servicio de dominio: utilidades puras para presentar metadatos de previsualización.

Funciones deterministas y testeables sin Qt ni infraestructura:
- Año de publicación desde upload_date crudo de yt-dlp ("20240815" -> "2024").
- Truncado de sinopsis respetando palabras.
- Tamaño humano para etiquetas de tamaño estimado.
"""

from typing import Optional

_MIN_YEAR = 1990
_MAX_YEAR = 2100
_DEFAULT_MAX_CHARS = 220
_ELLIPSIS = "..."


def extract_publication_year(upload_date: Optional[str]) -> str:
    """Extrae el año de publicación a partir del upload_date crudo de yt-dlp.

    yt-dlp devuelve fechas tipo "YYYYMMDD". Devuelve "" si no es parseable o
    está fuera de un rango razonable.
    """
    if not upload_date:
        return ""
    digits = "".join(ch for ch in str(upload_date) if ch.isdigit())
    if len(digits) < 4:
        return ""
    year_str = digits[:4]
    try:
        year = int(year_str)
    except ValueError:
        return ""
    if _MIN_YEAR <= year <= _MAX_YEAR:
        return year_str
    return ""


def truncate_text(text: Optional[str], max_chars: int = _DEFAULT_MAX_CHARS) -> str:
    """Trunca un texto largo en un límite de caracteres sin cortar palabras.

    Devuelve "" para entradas vacías. Si el texto excede max_chars, corta en el
    último espacio útil y agrega ellipsis.
    """
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_chars:
        return cleaned

    limit = max(1, max_chars - len(_ELLIPSIS))
    cut = cleaned[:limit]
    last_space = cut.rfind(" ")
    if last_space >= int(limit * 0.5):
        cut = cut[:last_space]
    return cut.rstrip(",;:. ") + _ELLIPSIS


def format_duration_seconds(duration_seconds: Optional[float]) -> str:
    """Convierte segundos en formato MM:SS o HH:MM:SS."""
    if not duration_seconds or duration_seconds <= 0:
        return ""
    total_seconds = int(duration_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_size_bytes(size_bytes: Optional[int]) -> str:
    """Convierte bytes a texto humano ("84 MB"). Devuelve "" si no hay dato."""
    if size_bytes is None or size_bytes <= 0:
        return ""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.0f} {unit}" if size >= 100 else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"
