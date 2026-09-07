"""Detección de navegadores instalados en el sistema para extracción de cookies."""
import os
import sys
from typing import List, Optional

_BROWSER_PATHS: dict[str, dict[str, list[str]]] = {
    "chrome": {
        "win32": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"),
        ],
        "darwin": [os.path.expanduser("~/Library/Application Support/Google/Chrome")],
        "linux": [os.path.expanduser("~/.config/google-chrome")],
    },
    "edge": {
        "win32": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data"),
        ],
        "darwin": [os.path.expanduser("~/Library/Application Support/Microsoft Edge")],
        "linux": [os.path.expanduser("~/.config/microsoft-edge")],
    },
    "firefox": {
        "win32": [
            os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox"),
        ],
        "darwin": [os.path.expanduser("~/Library/Application Support/Firefox")],
        "linux": [os.path.expanduser("~/.mozilla/firefox")],
    },
    "brave": {
        "win32": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data"),
        ],
        "darwin": [os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser")],
        "linux": [os.path.expanduser("~/.config/BraveSoftware/Brave-Browser")],
    },
}

# Orden de preferencia para auto-reintento con cookies
PREFERRED_BROWSER_ORDER: list[str] = ["firefox", "chrome", "brave", "edge"]


def detect_installed_browsers(platform_sys: Optional[str] = None) -> List[str]:
    """Retorna una lista de identificadores de navegadores detectados en el sistema."""
    plat = platform_sys or sys.platform
    detected: List[str] = []
    for browser_name, platform_paths in _BROWSER_PATHS.items():
        paths = platform_paths.get(plat, [])
        if any(os.path.isdir(p) for p in paths if p):
            detected.append(browser_name)
    return detected


def get_first_available_browser(preferred: Optional[str] = None) -> Optional[str]:
    """Retorna el primer navegador disponible según el orden de preferencia o el preferido."""
    detected = detect_installed_browsers()
    if not detected:
        return None

    if preferred and preferred.lower() in detected:
        return preferred.lower()

    for candidate in PREFERRED_BROWSER_ORDER:
        if candidate in detected:
            return candidate

    return detected[0]
