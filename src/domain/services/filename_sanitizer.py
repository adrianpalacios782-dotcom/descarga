import re

_INVALID_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_FILENAME_LENGTH = 180

_WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})


def sanitize_filename(name: str, fallback: str = "descarga", max_length: int = _MAX_FILENAME_LENGTH) -> str:
    """Sanitiza una cadena para ser usada de manera segura como nombre de archivo en Windows.

    - Reemplaza caracteres prohibidos (<>:"/\\|?* y caracteres de control ASCII) con guiones bajos.
    - Elimina espacios y puntos al inicio y al final.
    - Protege contra nombres de dispositivo reservados en Windows (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
    - Evita nombres vacíos usando el fallback.
    - Trunca al límite máximo de caracteres para no exceder los límites del sistema de archivos.
    """
    if not name:
        return fallback

    cleaned = _INVALID_CHARS_PATTERN.sub("_", name)
    cleaned = cleaned.strip().rstrip(". ")
    if not cleaned:
        return fallback

    if cleaned.upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"

    return cleaned[:max_length]
