"""Configuración del gestor dinámico del motor yt-dlp.

REGLAS DE SEGURIDAD:
- Las fuentes están FIJADAS aquí por constantes: GitHub Releases oficial de
  yt-dlp (primaria) y PyPI JSON API (fallback). Nunca provienen de entrada del
  usuario, archivos de configuración editables ni argumentos.
- Solo HTTPS. Solo hosts en las listas de permitidos.
- No hay tokens, cookies ni datos personales: la consulta es un GET anónimo.
"""
import re

# --- Fuente primaria: GitHub Releases oficial de yt-dlp ---------------------
YTDLP_GITHUB_OWNER = "yt-dlp"
YTDLP_GITHUB_REPO = "yt-dlp"

# URL canónica de metadatos del último release estable (API oficial, sin scraping).
GITHUB_RELEASES_API_URL = (
    f"https://api.github.com/repos/{YTDLP_GITHUB_OWNER}/{YTDLP_GITHUB_REPO}/releases/latest"
)

# --- Fuente alternativa: PyPI JSON API ---------------------------------------
PYPI_JSON_API_URL = "https://pypi.org/pypi/yt-dlp/json"

# Hosts desde los que se acepta METADATA (JSON de versiones).
ALLOWED_METADATA_HOSTS = frozenset({"api.github.com", "pypi.org"})

# Hosts desde los que se acepta DESCARGAR la wheel y archivos de checksums.
# github.com sirve /releases/download/<tag>/<asset> y redirige (302) hacia
# objects/release-assets.githubusercontent.com; PyPI sirve los artefactos
# desde files.pythonhosted.org.
ALLOWED_ASSET_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "files.pythonhosted.org",
    }
)

# Patrón estricto del asset wheel universal de yt-dlp. Captura la versión
# calendario (p. ej. "2026.08.19" o "2023.12.30.1") para anti path-traversal
# y para derivar SIEMPRE el nombre local a partir de un nombre validado.
WHEEL_ASSET_PATTERN = re.compile(
    r"^yt_dlp-(\d{4}\.\d{2}\.\d{2}(?:\.\d+)?)-py3-none-any\.whl$"
)

# Nombres admitidos para el archivo de checksums publicado en el release.
CHECKSUM_ASSET_NAMES = ("SHA2-256SUMS", "SHA256SUMS.txt", "SHA256SUMS", "checksums.txt")

# Formato de línea de checksum: "<hex64>  <nombre>" (sha256sum / Get-FileHash).
CHECKSUM_LINE_PATTERN = re.compile(r"^([0-9a-fA-F]{64})[\s\*]+(.+?)\s*$")

# --- Límites y timeouts ------------------------------------------------------
CONNECT_TIMEOUT_S = 10          # consulta de metadatos / checksums
DOWNLOAD_READ_TIMEOUT_S = 30    # timeout de lectura entre chunks
DOWNLOAD_CHUNK_SIZE = 64 * 1024

# Cota superior de seguridad para el tamaño de la wheel (~4 MB reales). Evita
# descargas descontroladas si la fuente estuviera comprometida.
MAX_WHEEL_BYTES = 64 * 1024 * 1024

# Cotas para payloads pequeños vía http_client.fetch_bytes.
MAX_JSON_BYTES = 1024 * 1024
MAX_CHECKSUM_FILE_BYTES = 256 * 1024


def is_allowed_metadata_url(url: str) -> bool:
    """True si `url` es HTTPS con host exactamente en ALLOWED_METADATA_HOSTS."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    return parsed.hostname.lower() in ALLOWED_METADATA_HOSTS


def is_allowed_asset_url(url: str) -> bool:
    """True si `url` es HTTPS con host exactamente en ALLOWED_ASSET_HOSTS."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    return parsed.hostname.lower() in ALLOWED_ASSET_HOSTS
