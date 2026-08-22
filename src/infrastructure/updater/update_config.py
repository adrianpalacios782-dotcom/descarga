"""Configuración del sistema de actualización.

REGLAS DE SEGURIDAD:
- La fuente de actualizaciones está FIJADA aquí por constantes. Nunca proviene
  de entrada del usuario, archivos de configuración editables ni argumentos.
- Solo HTTPS. Solo hosts en las listas de permitidos.
- No hay tokens, cookies ni datos personales: la consulta es un GET anónimo.
"""
import re

# --- Fuente oficial (GitHub Releases) --------------------------------------
GITHUB_OWNER = "adrianpalacios782-dotcom"
GITHUB_REPO = "descarga"

# URL canónica de metadatos del último release (API oficial, no scraping HTML).
RELEASES_API_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)

# Hosts desde los que se acepta METADATA (JSON de la API).
ALLOWED_METADATA_HOSTS = frozenset({"api.github.com"})

# Hosts desde los que se acepta DESCARGAR assets del instalador.
# github.com sirve /releases/download/<tag>/<asset> y redirige (302) hacia
# objects.githubusercontent.com o release-assets.githubusercontent.com.
ALLOWED_ASSET_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
)

# Patrón estricto que debe cumplir el nombre del asset instalador de Windows.
INSTALLER_ASSET_PATTERN = re.compile(
    r"^osvaldoDownloaderPro-(\d+\.\d+\.\d+)-Setup\.exe$"
)

# Nombres admitidos para el archivo de checksums publicado junto al instalador.
CHECKSUM_ASSET_NAMES = ("SHA256SUMS.txt", "SHA256SUMS", "checksums.txt")

# Formato de línea de checksum: "<hex64>  <nombre>" (salida de sha256sum /
# Get-FileHash formateada), con separadores de dos espacios o espacio+asterisco.
CHECKSUM_LINE_PATTERN = re.compile(
    r"^([0-9a-fA-F]{64})[\s\*]+(.+?)\s*$"
)

# --- Límites y timeouts -----------------------------------------------------
CONNECT_TIMEOUT_S = 10          # consulta de metadatos al iniciar
DOWNLOAD_READ_TIMEOUT_S = 30    # timeout de lectura entre chunks
DOWNLOAD_CHUNK_SIZE = 64 * 1024

# Cota superior de seguridad para el tamaño del instalador (~600 MB). Evita
# descargas descontroladas si el manifest estuviera comprometido.
MAX_INSTALLER_BYTES = 600 * 1024 * 1024

# Encabezados anónimos exigidos por la API de GitHub.
HTTP_HEADERS = {
    "User-Agent": "osvaldoDownloaderPro-Updater",
    "Accept": "application/vnd.github+json",
}

# Prefijo del directorio temporal de actualizaciones bajo %TEMP%.
TEMP_DIR_PREFIX = "osvaldoDownloaderPro-update-"

# Nombre local fijo del instalador dentro del directorio temporal seguro.
LOCAL_INSTALLER_FILENAME = "osvaldoDownloaderPro-Setup.exe"


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
